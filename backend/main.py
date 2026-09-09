import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from .models import TriageRequest, TriageResponse
from .agent import TriageAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(
    title="IBM Power Porting Triage Agent API",
    description="Agentic AI Prototype for qualifying application migrations to IBM Power (ppc64le)",
    version="1.0.0"
)

# Enable CORS for local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "IBM Power Porting Triage Agent", "version": "1.0.0"}


@app.get("/api/sample-workloads")
async def get_sample_workloads():
    """Returns realistic curated enterprise workloads for instant demo testing."""
    return [
        {
            "id": "microservices",
            "name": "Enterprise Cloud Microservices",
            "description": "Standard containerized enterprise application stack (Nginx, Redis, PostgreSQL, Kafka, Node.js, Spring Boot).",
            "target_os": "rhel9",
            "target_platform": "ocp",
            "manifest_type": "dockerfile",
            "content": """# ACME Payments Microservices Manifest
FROM nginx:1.24
FROM redis:7.2
FROM postgres:15
FROM quay.io/strimzi/kafka:latest
FROM node:20-alpine

# Java backend service
# artifactId: spring-boot-starter-web / version: 3.2.0
# artifactId: postgresql / version: 42.6.0
"""
        },
        {
            "id": "aiml_pipeline",
            "name": "AI/ML Data Pipeline (with Vector Acceleration)",
            "description": "Python ML inference service using PyTorch, NumPy, FastAPI, and custom C++ vector kernel with AVX2.",
            "target_os": "rhel9",
            "target_platform": "powervm",
            "manifest_type": "requirements",
            "content": """# AI Inference Pipeline Dependencies
torch==2.1.0
numpy==1.26.0
pandas==2.1.0
scipy==1.11.0
fastapi==0.110.0
pydantic==2.6.0

# Native acceleration extension requiring build from source
libcustom-dsp-engine==1.2.0
"""
        },
        {
            "id": "unported_storage",
            "name": "High-Throughput Storage Engine (Dependency Iceberg)",
            "description": "Database engine relying on RocksDB and simdjson. Demonstrates 64KB page size sensitivities and transitive build-dependency scoping.",
            "target_os": "rhel9",
            "target_platform": "baremetal",
            "manifest_type": "text",
            "content": """Customer uses a high-throughput time-series cache:
- rocksdb 8.6 (Storage engine, depends on snappy, lz4, zlib, jemalloc)
- simdjson 3.6 (Fast JSON parsing with AVX2/AVX-512)
- redis 7.2
- zlib 1.2.11
"""
        },
        {
            "id": "legacy_proprietary",
            "name": "Legacy Financial Analytics (x86 Blocker)",
            "description": "Workload containing proprietary Intel-MKL and C++ analytics libraries. Tests risk detection and alternative recommendations.",
            "target_os": "rhel8",
            "target_platform": "powervm",
            "manifest_type": "text",
            "content": """Financial risk calculation batch job:
- intel-mkl (Intel Math Kernel Library for x86)
- python 3.9
- numpy 1.24
- scipy 1.10
- custom-risk-calc 2.0
"""
        }
    ]


@app.post("/api/triage", response_model=TriageResponse)
async def triage_workload(request: TriageRequest):
    agent = TriageAgent(api_key=request.gemini_api_key)
    final_data = None
    async for event in agent.run_triage_stream(request):
        if event["type"] == "result":
            final_data = event["data"]
            break

    if not final_data:
        raise HTTPException(status_code=500, detail="Failed to complete triage assessment")

    return final_data


@app.post("/api/triage/stream")
async def triage_workload_stream(request: TriageRequest):
    """Server-Sent Events (SSE) streaming endpoint returning real-time agent thoughts, tool calls, and final report."""
    agent = TriageAgent(api_key=request.gemini_api_key)

    async def event_generator():
        async for event in agent.run_triage_stream(request):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
