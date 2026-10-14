"""
power_env.py
Manages connectivity, system diagnostics, and command execution on IBM Power (ppc64le) target VMs.
Supports direct SSH connections with key/password authentication, as well as a high-fidelity
Mock/Demonstration mode for simulated porting runs.
"""

import os
import re
import sys
import json
import base64
import asyncio
import logging
import uuid
import tempfile
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, List

from .models import PowerVMConfig

logger = logging.getLogger("power_env")


class BasePowerEnvironment(ABC):
    """Abstract base class for IBM Power execution environments."""

    @abstractmethod
    async def connect(self) -> Dict[str, Any]:
        """Establish connection and gather system diagnostics."""
        pass

    @abstractmethod
    async def execute(self, cmd: str, timeout: int = 300) -> Tuple[int, str, str]:
        """Execute command on target Power VM. Returns (exit_code, stdout, stderr)."""
        pass

    @abstractmethod
    async def write_file(self, remote_path: str, content: str) -> None:
        """Write text content to a file on the target environment."""
        pass

    @abstractmethod
    async def read_file(self, remote_path: str) -> str:
        """Read text content from a file on the target environment."""
        pass

    @abstractmethod
    async def create_build_container(
        self,
        image: str,
        container_name: str,
        host_workspace: str,
        engine: str = "auto"
    ) -> Dict[str, Any]:
        """Create and start an isolated build container on the target Power VM."""
        pass

    @abstractmethod
    async def exec_in_container(
        self,
        container_name: str,
        cmd: str,
        timeout: int = 300,
        workdir: Optional[str] = None
    ) -> Tuple[int, str, str]:
        """Execute command inside the target container. Returns (exit_code, stdout, stderr)."""
        pass

    @abstractmethod
    async def stop_and_remove_container(
        self,
        container_name: str,
        engine: str = "auto"
    ) -> None:
        """Stop and remove the container on the target environment."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up connection and resources."""
        pass


class SSHPowerEnvironment(BasePowerEnvironment):
    """Executes commands and transfers files to a real Power VM over OpenSSH."""

    def __init__(self, config: PowerVMConfig):
        self.config = config
        self.key_temp_file: Optional[str] = None
        self._sys_info: Dict[str, Any] = {}

    def _build_ssh_args(self) -> List[str]:
        args = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=15",
            "-o", "BatchMode=yes",
            "-p", str(self.config.port),
        ]
        if self.config.private_key:
            if not self.key_temp_file:
                tf = tempfile.NamedTemporaryFile(mode="w", delete=False, prefix="power_key_")
                tf.write(self.config.private_key.strip() + "\n")
                tf.close()
                os.chmod(tf.name, 0o600)
                self.key_temp_file = tf.name
            args.extend(["-i", self.key_temp_file])

        args.append(f"{self.config.username}@{self.config.host}")
        return args

    async def connect(self) -> Dict[str, Any]:
        logger.info("Connecting to Power VM at %s:%d as %s", self.config.host, self.config.port, self.config.username)

        # Probe system architecture and key attributes
        probe_script = """
        echo "===ARCH==="; uname -m
        echo "===KERNEL==="; uname -r
        echo "===PAGESIZE==="; getconf PAGESIZE 2>/dev/null || echo "65536"
        echo "===CPU==="; grep -m 1 -E 'cpu|model name' /proc/cpuinfo 2>/dev/null || echo "IBM POWER"
        echo "===VSX==="; grep -q -i vsx /proc/cpuinfo 2>/dev/null && echo "enabled" || echo "not detected"
        echo "===MMA==="; grep -q -i mma /proc/cpuinfo 2>/dev/null && echo "enabled" || echo "not detected"
        echo "===OS==="; (cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '"') 2>/dev/null || uname -s
        echo "===GCC==="; gcc --version 2>/dev/null | head -n 1 || echo "not installed"
        echo "===PYTHON==="; python3 --version 2>/dev/null || echo "not installed"
        echo "===CONTAINER==="; (podman --version 2>/dev/null || docker --version 2>/dev/null) | head -n 1 || echo "none"
        """

        code, stdout, stderr = await self.execute(probe_script, timeout=30)
        if code != 0:
            raise ConnectionError(f"Failed to connect to Power VM at {self.config.host}:{self.config.port}: {stderr or stdout}")

        info: Dict[str, Any] = {
            "host": self.config.host,
            "port": self.config.port,
            "username": self.config.username,
            "architecture": "ppc64le",
            "page_size": "65536",
            "vsx_support": True,
            "mma_support": False,
            "os": "Red Hat Enterprise Linux",
            "compiler": "gcc",
            "python": "Python 3.9+",
            "container_engine": "podman",
        }

        # Parse probed output
        sections = stdout.split("===")
        for i in range(1, len(sections), 2):
            if i + 1 < len(sections):
                key = sections[i].strip()
                val = sections[i + 1].strip()
                if key == "ARCH":
                    info["architecture"] = val
                elif key == "KERNEL":
                    info["kernel"] = val
                elif key == "PAGESIZE":
                    info["page_size"] = val
                elif key == "CPU":
                    info["cpu_model"] = val
                elif key == "VSX":
                    info["vsx_support"] = (val == "enabled")
                elif key == "MMA":
                    info["mma_support"] = (val == "enabled")
                elif key == "OS":
                    info["os"] = val
                elif key == "GCC":
                    info["compiler"] = val
                elif key == "PYTHON":
                    info["python"] = val
                elif key == "CONTAINER":
                    info["container_engine"] = val

        self._sys_info = info
        logger.info("Successfully probed Power VM: %s on %s (page size: %s)", info.get("architecture"), info.get("os"), info.get("page_size"))
        return info

    async def execute(self, cmd: str, timeout: int = 300) -> Tuple[int, str, str]:
        ssh_cmd = self._build_ssh_args() + [cmd]
        try:
            proc = await asyncio.create_subprocess_exec(
                *ssh_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            exit_code = proc.returncode or 0
            return exit_code, stdout_data.decode("utf-8", errors="replace"), stderr_data.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return 124, "", f"Command timed out after {timeout} seconds"
        except Exception as e:
            return 1, "", str(e)

    async def write_file(self, remote_path: str, content: str) -> None:
        # Encode via base64 to avoid quoting and escape issues over remote shell
        b64_content = base64.b64encode(content.encode("utf-8")).decode("ascii")
        remote_dir = os.path.dirname(remote_path)
        cmd = f"mkdir -p '{remote_dir}' && echo '{b64_content}' | base64 -d > '{remote_path}'"
        code, out, err = await self.execute(cmd, timeout=30)
        if code != 0:
            raise IOError(f"Failed to write remote file {remote_path}: {err or out}")

    async def read_file(self, remote_path: str) -> str:
        cmd = f"cat '{remote_path}'"
        code, out, err = await self.execute(cmd, timeout=30)
        if code != 0:
            raise IOError(f"Failed to read remote file {remote_path}: {err or out}")
        return out

    async def _resolve_container_engine(self, engine: str = "auto") -> str:
        if engine and engine.lower() in ("podman", "docker"):
            return engine.lower()
        code, out, _ = await self.execute("command -v podman || command -v docker")
        if code == 0 and "podman" in out:
            return "podman"
        elif code == 0 and "docker" in out:
            return "docker"
        return "podman"

    async def create_build_container(
        self,
        image: str,
        container_name: str,
        host_workspace: str,
        engine: str = "auto"
    ) -> Dict[str, Any]:
        rt_engine = await self._resolve_container_engine(engine)
        logger.info("Spawning build container '%s' with image '%s' on Power VM via %s", container_name, image, rt_engine)

        # Ensure host workspace exists on the target Power VM
        await self.execute(f"mkdir -p '{host_workspace}'")

        # Clean up any leftover container with the same name
        await self.execute(f"{rt_engine} rm -f '{container_name}' 2>/dev/null || true")

        # Pull image and start detached container with host workspace mounted
        run_cmd = (
            f"{rt_engine} run -d "
            f"--name '{container_name}' "
            f"-v '{host_workspace}:/workspace:z' "
            f"-w /workspace "
            f"'{image}' sleep infinity"
        )
        code, out, err = await self.execute(run_cmd, timeout=180)
        if code != 0:
            raise RuntimeError(f"Failed to launch build container '{container_name}' on Power VM: {err or out}")

        cid = out.strip()[:12] if out else container_name

        # Query container OS
        probe_os_cmd = f"{rt_engine} exec '{container_name}' sh -c '(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d \\\"\\') 2>/dev/null || uname -s'"
        _, os_name, _ = await self.execute(probe_os_cmd, timeout=30)
        os_label = os_name.strip() or "Linux (ppc64le container)"

        # Query container package manager
        probe_pm_cmd = f"{rt_engine} exec '{container_name}' sh -c 'command -v dnf || command -v microdnf || command -v yum || command -v apt-get || echo unknown'"
        _, pm_out, _ = await self.execute(probe_pm_cmd, timeout=30)
        pm_path = pm_out.strip()
        pkg_manager = "dnf"
        if "apt-get" in pm_path:
            pkg_manager = "apt-get"
        elif "microdnf" in pm_path:
            pkg_manager = "microdnf"
        elif "yum" in pm_path:
            pkg_manager = "yum"

        return {
            "container_id": cid,
            "container_name": container_name,
            "image": image,
            "engine": rt_engine,
            "os_name": os_label,
            "package_manager": pkg_manager,
            "workspace": "/workspace",
        }

    async def exec_in_container(
        self,
        container_name: str,
        cmd: str,
        timeout: int = 300,
        workdir: Optional[str] = None
    ) -> Tuple[int, str, str]:
        rt_engine = await self._resolve_container_engine(self.config.container_engine)
        workdir_arg = f"-w '{workdir}' " if workdir else ""
        b64_cmd = base64.b64encode(cmd.encode("utf-8")).decode("ascii")
        remote_exec_cmd = (
            f"{rt_engine} exec -i {workdir_arg}'{container_name}' "
            f"sh -c 'echo \"{b64_cmd}\" | base64 -d | (bash -l 2>/dev/null || sh)'"
        )
        return await self.execute(remote_exec_cmd, timeout=timeout)

    async def stop_and_remove_container(
        self,
        container_name: str,
        engine: str = "auto"
    ) -> None:
        rt_engine = await self._resolve_container_engine(engine)
        await self.execute(f"{rt_engine} rm -f '{container_name}' 2>/dev/null || true", timeout=30)

    async def close(self) -> None:
        if self.key_temp_file and os.path.exists(self.key_temp_file):
            try:
                os.remove(self.key_temp_file)
            except Exception:
                pass
            self.key_temp_file = None


class MockPowerEnvironment(BasePowerEnvironment):
    """
    High-fidelity simulated IBM Power10 (ppc64le) environment for testing, verification,
    and end-to-end demonstrations without requiring immediate physical hardware.
    """

    def __init__(self, config: PowerVMConfig):
        self.config = config
        self._sys_info: Dict[str, Any] = {}
        self._files: Dict[str, str] = {}
        self._build_attempt: int = 0
        self._workspace: str = config.workspace_dir or "/tmp/power_porting"

    async def connect(self) -> Dict[str, Any]:
        await asyncio.sleep(0.5)  # Simulate network handshake
        self._sys_info = {
            "host": self.config.host if self.config.host != "127.0.0.1" else "powervs-dal10-p10-lpar01.ibm.com",
            "port": self.config.port,
            "username": self.config.username,
            "architecture": "ppc64le",
            "kernel": "5.14.0-427.18.1.el9_4.ppc64le",
            "page_size": "65536 (64KB Enterprise Linux default)",
            "cpu_model": "POWER10 (raw), altivec supported, 3.50 GHz",
            "vsx_support": True,
            "mma_support": True,
            "os": "Red Hat Enterprise Linux 9.4 (Plow) ppc64le",
            "compiler": "gcc (GCC) 11.4.1 20231218 (Red Hat 11.4.1-3)",
            "python": "Python 3.9.18",
            "container_engine": "podman version 4.9.4-rhel",
            "simulated": True,
        }
        return self._sys_info

    async def execute(self, cmd: str, timeout: int = 300) -> Tuple[int, str, str]:
        await asyncio.sleep(0.3)  # Realistic latency

        cmd_clean = cmd.strip()

        # Handle directory creation / checking
        if "mkdir -p" in cmd_clean:
            return 0, "Directory created", ""

        # Git clone or checkout
        if "git clone" in cmd_clean:
            return 0, f"Cloning into repository in {self._workspace}...\nremote: Enumerating objects: 1420, done.\nremote: Total 1420 (delta 0), reused 0 (delta 0)\nReceiving objects: 100% (1420/1420), done.", ""

        # Prerequisite package install
        if "dnf install" in cmd_clean or "yum install" in cmd_clean or "apt-get install" in cmd_clean:
            return 0, "Dependencies resolved.\nInstalling: gcc-c++, cmake, python3-devel, libstdc++-devel, simde-devel\nComplete!", ""

        # Build execution
        if any(b in cmd_clean for b in ["pip wheel", "python -m build", "cmake --build", "podman build", "make", "cargo build"]):
            self._build_attempt += 1

            # Check if an architecture patch was applied
            has_patch = any("__powerpc__" in content or "SIMDe" in content or "sysconf(_SC_PAGESIZE)" in content for content in self._files.values())

            if not has_patch and self._build_attempt == 1:
                # First attempt fails realistically with x86-specific SIMD or page size errors
                if "container" in cmd_clean or "podman" in cmd_clean:
                    stderr = (
                        "STEP 4/7: RUN gcc -O3 -mavx2 -o engine src/vector_ops.c\n"
                        "In file included from src/vector_ops.c:12:\n"
                        "/usr/lib/gcc/ppc64le-redhat-linux/11/include/immintrin.h: fatal error: immintrin.h: No such file or directory\n"
                        "   12 | #include <immintrin.h>\n"
                        "      |          ^~~~~~~~~~~~~\n"
                        "compilation terminated on ppc64le target.\n"
                        "Error: building at STEP 'RUN gcc -O3 -mavx2 -o engine src/vector_ops.c': exit code 1"
                    )
                    return 1, "", stderr
                elif "wheel" in cmd_clean or "build" in cmd_clean:
                    stderr = (
                        "running bdist_wheel\n"
                        "running build_ext\n"
                        "building 'accelerated_kernel' extension\n"
                        "gcc -pthread -B /usr/lib/rpm/redhat -fno-strict-aliasing -O2 -g -pipe -Wall -fPIC -I/usr/include/python3.9 -c src/simd_accel.cpp -o build/simd_accel.o\n"
                        "src/simd_accel.cpp:18:10: fatal error: immintrin.h: No such file or directory\n"
                        "   18 | #include <immintrin.h>\n"
                        "      |          ^~~~~~~~~~~~~\n"
                        "src/simd_accel.cpp:45:25: error: '__m256i' was not declared in this scope; did you mean '__vector signed int'?\n"
                        "   45 | static inline void load(__m256i *dest, const int32_t *src) {\n"
                        "      |                         ^~~~~~~\n"
                        "error: command '/usr/bin/gcc' failed with exit code 1"
                    )
                    return 1, "", stderr
                else:
                    stderr = (
                        "CMake Error at CMakeLists.txt:48 (message):\n"
                        "  Unsupported architecture ppc64le without VSX/Altivec mapping! Hardcoded AVX2 intrinsics required.\n"
                        "FAILED: CMakeFiles/core.dir/src/cache.cpp.o\n"
                        "src/cache.cpp:32:15: error: static assertion failed: PAGE_SIZE assumption 4096 failed (ppc64le kernel is 65536)\n"
                        "   32 | static_assert(PAGE_SIZE == 4096, \"Fixed 4KB page size assumed in buffer pool\");\n"
                    )
                    return 1, "", stderr

            # With patch applied or on retry, compilation succeeds!
            stdout = (
                "[1/5] Building ppc64le VSX accelerated vector kernels...\n"
                "[2/5] Compiling with -mcpu=power9 -mtune=power10 -maltivec -mvsx -D__PPC64__...\n"
                "[3/5] Dynamic 64KB page size detection sysconf(_SC_PAGESIZE) active.\n"
                "[4/5] Successfully compiled native extension on ppc64le.\n"
                "[5/5] Creating deliverable artifact...\n"
            )
            if "wheel" in cmd_clean:
                stdout += "Successfully built wheel: dist/accelerated_kernel-1.2.0-cp39-cp39-linux_ppc64le.whl\n"
            elif "podman" in cmd_clean or "container" in cmd_clean:
                stdout += "Successfully tagged localhost/accelerated_kernel:1.2.0-ppc64le\n[STEP 7/7] COMMIT localhost/accelerated_kernel:1.2.0-ppc64le\n"
            else:
                stdout += "Built target release/accelerated_kernel (ppc64le ELF 64-bit LSB shared object)\n"
            return 0, stdout, ""

        # Test execution
        if any(t in cmd_clean for t in ["pytest", "ctest", "cargo test", "npm test", "make test"]):
            stdout = (
                "============================= test session starts ==============================\n"
                "platform linux -- Python 3.9.18, pytest-8.1.1, pluggy-1.4.0\n"
                "rootdir: /tmp/power_porting/workload\n"
                "collected 18 items\n\n"
                "tests/test_kernel.py::test_vector_ops_vsx PASSED                         [ 16%]\n"
                "tests/test_kernel.py::test_precision_vsx_vs_scalar PASSED                [ 33%]\n"
                "tests/test_kernel.py::test_64kb_page_alignment PASSED                    [ 50%]\n"
                "tests/test_kernel.py::test_endianness_byte_ordering PASSED              [ 66%]\n"
                "tests/test_kernel.py::test_cross_platform_compat PASSED                  [ 83%]\n"
                "tests/test_kernel.py::test_stress_concurrency PASSED                     [100%]\n\n"
                "============================== 18 passed in 1.42s ==============================\n"
            )
            return 0, stdout, ""

        # Git branch and status commands
        if "git" in cmd_clean:
            return 0, "Switched to a new branch 'port/ppc64le-support'\n[port/ppc64le-support 4b7a1f2] feat(ppc64le): add IBM Power architecture support\n 2 files changed, 48 insertions(+), 6 deletions(-)", ""

        return 0, f"Simulated execution succeeded: {cmd_clean[:60]}...", ""

    async def write_file(self, remote_path: str, content: str) -> None:
        self._files[remote_path] = content

    async def read_file(self, remote_path: str) -> str:
        if remote_path in self._files:
            return self._files[remote_path]
        return f"# Sample file at {remote_path}\n"

    async def create_build_container(
        self,
        image: str,
        container_name: str,
        host_workspace: str,
        engine: str = "auto"
    ) -> Dict[str, Any]:
        os_label = "Red Hat Universal Base Image 9.4 (Plow) ppc64le"
        if "ubuntu" in image.lower():
            os_label = "Ubuntu 22.04.4 LTS (Jammy Jellyfish) ppc64le"
        elif "fedora" in image.lower():
            os_label = "Fedora Linux 40 (Container Image) ppc64le"
        elif "debian" in image.lower():
            os_label = "Debian GNU/Linux 12 (bookworm) ppc64le"

        pkg_mgr = "apt-get" if ("ubuntu" in image.lower() or "debian" in image.lower()) else "dnf"
        return {
            "container_id": f"cont-{uuid.uuid4().hex[:8]}",
            "container_name": container_name,
            "image": image,
            "engine": "podman",
            "os_name": os_label,
            "package_manager": pkg_mgr,
            "workspace": "/workspace",
        }

    async def exec_in_container(
        self,
        container_name: str,
        cmd: str,
        timeout: int = 300,
        workdir: Optional[str] = None
    ) -> Tuple[int, str, str]:
        return await self.execute(cmd, timeout=timeout)

    async def stop_and_remove_container(
        self,
        container_name: str,
        engine: str = "auto"
    ) -> None:
        pass

    async def close(self) -> None:
        pass


def get_power_environment(config: PowerVMConfig) -> BasePowerEnvironment:
    """Factory creating the Power environment; uses real SSHPowerEnvironment for all real hosts."""
    if getattr(config, "use_mock", False) and config.host == "mock":
        logger.info("Initializing MockPowerEnvironment for test suite fixture")
        return MockPowerEnvironment(config)
    return SSHPowerEnvironment(config)

