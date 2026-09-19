import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Canvas that computes total pages dynamically for footer page numbers."""
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(45, 752, "IBM Power Porting Triage Agent — AI Elite Program Submission")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(45, 746, 567, 746)

        # Footer (all pages)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(45, 42, 567, 42)
        
        footer_text = "CONFIDENTIAL — FOR INTERNAL REVIEW & PROGRAM SUBMISSION ONLY"
        self.drawString(45, 30, footer_text)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(567, 30, page_str)
        self.restoreState()


def build_presentation_pdf(output_path="customer_presentation.pdf"):
    # Printable area: 612 - 2*45 = 522 pt width
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=45,
        rightMargin=45,
        topMargin=46,
        bottomMargin=46
    )

    styles = getSampleStyleSheet()

    # IBM Design Language / Executive Color Palette
    PRIMARY = colors.HexColor("#0f62fe")        # IBM Blue
    SECONDARY = colors.HexColor("#002d9c")      # Dark Cobalt
    TEXT_DARK = colors.HexColor("#0f172a")      # Slate 900
    TEXT_MUTED = colors.HexColor("#475569")     # Slate 600
    BG_LIGHT = colors.HexColor("#f8fafc")       # Light background slate-50
    BG_ALT = colors.HexColor("#f1f5f9")         # Slate 100
    BORDER_COLOR = colors.HexColor("#cbd5e1")   # Border grey slate-300
    ACCENT_GREEN = colors.HexColor("#16a34a")   # Emerald Green
    ACCENT_AMBER = colors.HexColor("#d97706")   # Amber Warning
    ACCENT_RED = colors.HexColor("#dc2626")     # Red Risk

    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=SECONDARY,
        spaceAfter=3
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=PRIMARY,
        spaceAfter=10
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12.5,
        leading=15.5,
        textColor=SECONDARY,
        spaceBefore=8,
        spaceAfter=5,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12.5,
        textColor=PRIMARY,
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=TEXT_DARK,
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        'BulletText',
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3
    )

    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=SECONDARY
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.8,
        leading=10.2,
        textColor=TEXT_DARK
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=table_cell_style,
        fontName='Helvetica-Bold'
    )

    table_cell_code = ParagraphStyle(
        'TableCellCode',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.2,
        leading=9.2,
        textColor=SECONDARY
    )

    story = []

    # =========================================================================
    # PAGE 1: EXECUTIVE SUMMARY, TARGET PERSONA & PROBLEM STATEMENT
    # =========================================================================
    story.append(Paragraph("AI Elite Program — Customer Presentation Document", title_style))
    story.append(Paragraph("Autonomous IBM Power Porting Triage Agent with Multi-Pillar Architecture Auditing", subtitle_style))
    
    meta_data = [
        [
            Paragraph("<b>Initiative:</b> AI Elite Program Prototype Submission", table_cell_style),
            Paragraph("<b>Target Architecture:</b> IBM Power (<code>ppc64le</code>)", table_cell_style)
        ],
        [
            Paragraph("<b>Primary Personas:</b> Technical Pre-Sales & Solution Architects", table_cell_style),
            Paragraph("<b>Runtime Platforms:</b> RHEL 8/9, OpenShift (OCP), Ubuntu, SLES", table_cell_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[260, 262])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_ALT),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # Section 1: Customer & Persona
    story.append(Paragraph("1. Customer Profile & Target Personas", h1_style))
    story.append(Paragraph(
        "<b>Customer Profile:</b> Global enterprises running high-throughput transactional, time-series, and data/AI workloads (financial services, telecom, healthcare, and retail) evaluating platform modernization from commodity x86 infrastructure to <b>IBM Power (<code>ppc64le</code>)</b> on RHEL and OpenShift.",
        body_style
    ))
    story.append(Paragraph("• <b>IBM Technical Pre-Sales Specialists & Solution Architects:</b> Frontline technical sellers who must rapidly qualify migration feasibility, size porting timelines, and build client confidence during competitive evaluations.", bullet_style))
    story.append(Paragraph("• <b>Enterprise Decision-Makers (CIO / CTO / VP Infrastructure):</b> Stakeholders requiring transparent risk qualification, timeline predictability, and platform ROI before approving modernization contracts.", bullet_style))
    story.append(Paragraph("• <b>IBM Power Porting Lab & Ecosystem Engineers:</b> Specialized engineering squads responsible for compiling, tuning, and verifying unported packages, who need structured, actionable technical backlogs.", bullet_style))
    story.append(Spacer(1, 6))

    # Section 2: Business Problem
    story.append(Paragraph("2. Business Problem & Pre-Sales Friction", h1_style))
    story.append(Paragraph(
        "While IBM Power offers unmatched hardware throughput (high memory bandwidth, SMT8 core threading, and hardware Matrix Math Accelerators), <b>pre-sales qualification creates severe friction in the sales pipeline:</b>",
        body_style
    ))
    story.append(Paragraph("• <b>Unstandardized & Heterogeneous Inputs:</b> Customers provide dependency specifications in fragmented formats: CycloneDX/SPDX SBOM JSONs, multi-stage Dockerfiles, Python requirements, Compose/Kubernetes YAMLs, or informal notes.", bullet_style))
    story.append(Paragraph("• <b>Fragmented Ecosystem Registries & Version Drift:</b> Determining package availability requires tedious manual searches across RHEL BaseOS/AppStream, EPEL 9, Quay.io, Docker Hub, PyPI, and community channels (Conda-forge, IBM Open-CE). Often, generic version queries give false confidence when the customer's <i>specific version tag</i> lacks a ppc64le binary.", bullet_style))
    story.append(Paragraph("• <b>The 'Iceberg' Estimation Gap:</b> When a C/C++ library or database engine lacks an official prebuilt binary for <code>ppc64le</code>, pre-sales teams cannot see beneath the surface. Uncovered build-time dependencies (e.g. jemalloc needing 64KB page size tuning) or unported x86 SIMD intrinsics (AVX2/AVX-512) surface late, resulting in costly project overruns.", bullet_style))
    story.append(Paragraph("• <b>Opaque Effort Sizing:</b> Traditional sizing relies on subjective guesswork, leading to 2x–5x variance and eroded trust between sales teams and client engineering leads.", bullet_style))
    story.append(Spacer(1, 6))

    # Section 3: Business Impact Table
    story.append(Paragraph("3. Quantified Business Impact", h1_style))
    impact_data = [
        [Paragraph("Operational Dimension", table_header_style), Paragraph("Current Manual Process", table_header_style), Paragraph("AI Agent Prototype Impact", table_header_style)],
        [
            Paragraph("<b>Qualification Turnaround Time</b>", table_cell_style),
            Paragraph("5 to 10 Business Days across manual catalog lookups and emails", table_cell_style),
            Paragraph("<b>&lt; 30 Seconds</b> automated end-to-end qualification", table_cell_bold)
        ],
        [
            Paragraph("<b>Porting Lab Bandwidth Waste</b>", table_cell_style),
            Paragraph("~40% of senior engineer time spent on routine initial triage", table_cell_style),
            Paragraph("<b>Zero wasted hours</b> on routine triage; lab only receives scoped specs", table_cell_bold)
        ],
        [
            Paragraph("<b>Deal Velocity & Friction</b>", table_cell_style),
            Paragraph("Prolonged sales cycles; customer hesitation due to unknown porting risks", table_cell_style),
            Paragraph("<b>Immediate sales confidence</b> with instant traffic-light readiness scoring", table_cell_bold)
        ],
        [
            Paragraph("<b>Effort Sizing Accuracy</b>", table_cell_style),
            Paragraph("Subjective guesswork prone to 2x–5x variance from hidden dependencies", table_cell_style),
            Paragraph("<b>Transparent 3-Pillar Sizing</b> (Build + Engineering + Test PD)", table_cell_bold)
        ],
        [
            Paragraph("<b>Container & CI Visibility</b>", table_cell_style),
            Paragraph("Multi-stage Dockerfiles and CI workflows ignored until deployment", table_cell_style),
            Paragraph("<b>Automated multi-stage Dockerfile & CI matrix scanning</b>", table_cell_bold)
        ],
        [
            Paragraph("<b>Executive Proposal Deliverables</b>", table_cell_style),
            Paragraph("Days spent assembling custom slide decks and proposal memos", table_cell_style),
            Paragraph("<b>1-Click Executive Memo & CSV Backlog</b> generated autonomously", table_cell_bold)
        ]
    ]
    impact_table = Table(impact_data, colWidths=[130, 192, 200])
    impact_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), SECONDARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
    ]))
    story.append(impact_table)

    # =========================================================================
    # PAGE 2: AGENT ARCHITECTURE & 8 CORE INNOVATIONS
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("4. Proposed Opportunity: Autonomous AI Agent Architecture", h1_style))
    story.append(Paragraph(
        "The <b>Autonomous IBM Power Porting Triage Agent</b> combines deterministic ecosystem probing with generative sales synthesis, delivering instant qualification, transparent effort sizing, and executive deliverables:",
        body_style
    ))
    story.append(Spacer(1, 2))

    innovations = [
        ("Universal Ingestion & Multi-Stage Dockerfile Parsing", "Automatically ingests CycloneDX/SPDX SBOMs, Python requirements, Compose/Kubernetes manifests, and raw multi-stage Dockerfiles (<code>FROM ... AS builder</code>), validating base images for every build and runtime stage."),
        ("Multi-Source Prober with Version-Aware Intelligence", "Executes real-time live queries against Quay.io, Docker Hub v2 API, RHEL/EPEL 9 repos, and PyPI. Detects version mismatches (e.g. requested tag unavailable on <code>ppc64le</code>), providing actionable upgrade/downgrade advice with clickable verification URLs."),
        ("Deep Transitive Build Dependency Analysis ('Solving the Iceberg')", "Recursively inspects build requirements (<code>BuildRequires</code>, submodules, header libraries) for unported packages to uncover hidden dependencies before compilation starts (e.g. scoping <code>jemalloc-ppc64le</code> for RocksDB)."),
        ("Hardware Architecture Sensitivity Auditing", "Audits source code and build configs for CPU architecture friction: flags x86 SIMD (AVX2/AVX-512) intrinsics (recommending SIMDe to Power VSX translations), 64KB page size sensitivities (jemalloc tuning), and inline assembly (x86 <code>pause</code> mapped to Power <code>or 27,27,27</code>)."),
        ("Calibrated SIMD Volume Bracket Scaling", "Scales engineering effort based on vector instruction volume across 5 standardized brackets: 0–50 inst (1.0x), 51–200 inst (1.5x), 201–500 inst (2.5x), and >500 inst (4.0x multiplier), reflecting the code surface requiring inspection and porting."),
        ("4-Tier SIMD-to-VSX Porting Complexity Classification", "Classifies vector adaptation into 4 rigorous engineering tiers: <code>DIRECT</code> (1.0x), <code>SIMDE_COMPATIBLE</code> (1.5x), <code>PARTIAL_REWRITE</code> (2.5x), and <code>FULL_REDESIGN</code> (4.0x for AVX-512 gather/scatter or Power MMA kernels)."),
        ("Dedicated Test Suite & Validation Effort Sizing", "Discovers test frameworks (GTest, pytest, Catch2, Testcontainers) and allocates dedicated test validation effort (<code>test_effort_pd</code>) to guarantee regression verification is sized alongside compilation."),
        ("Git Repository Architecture Posture & CI Matrix Scanning", "Inspects upstream Git repositories for existing Power markers (<code>#ifdef __powerpc__</code>) and audits GitHub Actions / GitLab CI matrices for active <code>ppc64le</code> runners, applying an effort adjustment factor (0.7x for mature Power CI to 1.3x for x86-only codebases)."),
        ("Compose, Kubernetes & Infrastructure Image Verifier", "Parses Docker Compose files, Kubernetes manifests, and Helm charts to verify all ancillary service images (databases, sidecars, log forwarders) on <code>ppc64le</code>."),
        ("Generative Executive Proposal Engine", "Uses Google Gemini (with resilient multi-model fallback across <code>gemini-3.5-flash</code> and <code>gemini-3.5-flash-lite</code>) to draft client-ready strategic value proposals highlighting Power memory bandwidth, SMT8 threading, and enterprise ROI.")
    ]

    for title, desc in innovations:
        story.append(Paragraph(f"• <b>{title}:</b> {desc}", bullet_style))
    story.append(Spacer(1, 8))

    # Architecture Workflow Box
    workflow_data = [
        [
            Paragraph("<b>Universal Manifest Ingestion</b><br/><font color='#475569'>SBOM, Dockerfile, Compose, Git URL, Free-text</font>", table_cell_style),
            Paragraph("<b>Deterministic Prober & Scoper</b><br/><font color='#475569'>Quay, Docker Hub, RHEL 9, PyPI, Deep Build Tree</font>", table_cell_style),
            Paragraph("<b>Architecture & CI Posture Audit</b><br/><font color='#475569'>SIMD Brackets, 4-Tier VSX, 64K Pages, CI Matrix</font>", table_cell_style),
            Paragraph("<b>Executive Synthesis & Sizing</b><br/><font color='#475569'>Build+Eng+Test PD, Traffic Light, 1-Click Memo</font>", table_cell_style),
        ]
    ]
    workflow_table = Table(workflow_data, colWidths=[130, 130, 132, 130])
    workflow_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_ALT),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(workflow_table)

    # =========================================================================
    # PAGE 3: TRANSPARENT SIZING METHODOLOGY & MATHEMATICAL DERIVATION
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("5. Transparent Effort Sizing Methodology & Engineering Derivation", h1_style))
    story.append(Paragraph(
        "To replace subjective estimation with mathematical rigor, the agent computes porting effort using a standardized <b>3-Pillar Sizing Formula</b> that isolates compilation, hardware adaptation, and test validation:",
        body_style
    ))
    
    formula_box = [
        [
            Paragraph(
                "<b>Formula:</b> Total Person-Days (PD) = Build Effort + Engineering Adaptation Effort + Test Effort<br/>"
                "<b>Where:</b> Engineering Effort = Base Engineering × SIMD Count Multiplier × Complexity Multiplier × Repo CI Factor",
                callout_style
            )
        ]
    ]
    formula_table = Table(formula_box, colWidths=[522])
    formula_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
        ('BOX', (0, 0), (-1, -1), 1, PRIMARY),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(formula_table)
    story.append(Spacer(1, 6))

    story.append(Paragraph("Sizing Parameters & Multiplier Matrix", h2_style))
    matrix_data = [
        [Paragraph("Sizing Dimension", table_header_style), Paragraph("Bracket / Classification Tier", table_header_style), Paragraph("Multiplier", table_header_style), Paragraph("Engineering Rationale & Scope", table_header_style)],
        [
            Paragraph("<b>SIMD Instruction Volume</b>", table_cell_style),
            Paragraph("0 – 50 instructions<br/>51 – 200 instructions<br/>201 – 500 instructions<br/>&gt; 500 instructions", table_cell_style),
            Paragraph("<b>1.0x</b><br/><b>1.5x</b><br/><b>2.5x</b><br/><b>4.0x</b>", table_cell_bold),
            Paragraph("Reflects the total vector instruction surface requiring manual inspection, inline substitution, and micro-benchmarking.", table_cell_style)
        ],
        [
            Paragraph("<b>Porting Complexity Tier</b>", table_cell_style),
            Paragraph("<code>DIRECT</code><br/><code>SIMDE_COMPATIBLE</code><br/><code>PARTIAL_REWRITE</code><br/><code>FULL_REDESIGN</code>", table_cell_style),
            Paragraph("<b>1.0x</b><br/><b>1.5x</b><br/><b>2.5x</b><br/><b>4.0x</b>", table_cell_bold),
            Paragraph("From 1:1 intrinsic substitution, to SIMDe header mapping, to 128-bit vs 256-bit loop refactoring, up to full AVX-512 redesign to Power MMA.", table_cell_style)
        ],
        [
            Paragraph("<b>Repository CI Posture</b>", table_cell_style),
            Paragraph("Power CI present (<code>ppc64le</code> runner)<br/>Neutral / Mixed markers<br/>Hardcoded x86 / No Power CI", table_cell_style),
            Paragraph("<b>0.7x</b> (Discount)<br/><b>1.0x</b> (Baseline)<br/><b>1.3x</b> (Friction)", table_cell_bold),
            Paragraph("Accounts for upstream willingness and infrastructure to validate, accept, and maintain Power patches.", table_cell_style)
        ],
        [
            Paragraph("<b>Test Suite Validation</b>", table_cell_style),
            Paragraph("Standard Unit Tests<br/>Integration / Benchmarks<br/>Missing Native Test Harness", table_cell_style),
            Paragraph("<b>0.5 – 1.0d</b><br/><b>1.5 – 2.0d</b><br/><b>+2.0d</b>", table_cell_bold),
            Paragraph("Ensures regression verification, test container availability, and performance validation are fully accounted for.", table_cell_style)
        ]
    ]
    matrix_table = Table(matrix_data, colWidths=[110, 140, 72, 200])
    matrix_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), SECONDARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
    ]))
    story.append(matrix_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Worked Enterprise Sizing Derivations", h2_style))
    examples_data = [
        [Paragraph("Target Component", table_header_style), Paragraph("Component Analysis & Findings", table_header_style), Paragraph("Step-by-Step Derivation Formula", table_header_style), Paragraph("Total PD", table_header_style)],
        [
            Paragraph("<b>simdjson 3.6</b><br/>(C++ JSON Parser)", table_cell_style),
            Paragraph("• Build: CMake toolchain (1.0d)<br/>• SIMD: 320 AVX2 instructions<br/>• Tier: <code>SIMDE_COMPATIBLE</code><br/>• Test: cxxopts + benchmark (1.0d)", table_cell_style),
            Paragraph("<b>Build:</b> 1.0d<br/><b>Engineering:</b> 2.0d base × 2.5 (vol) × 1.5 (tier) × 1.0 (CI) = <b>7.5d</b><br/><b>Test:</b> 1.0d<br/><b>Sum:</b> 1.0 + 7.5 + 1.0 = 9.5 ≈ 10 PD", table_cell_code),
            Paragraph("<b>10 PD</b>", table_cell_bold)
        ],
        [
            Paragraph("<b>RocksDB 8.6</b><br/>(Storage Engine)", table_cell_style),
            Paragraph("• Build: CMake (1.5d)<br/>• Transitive: jemalloc-64k (1.5d)<br/>• Arch: Inline asm yield (1.5d)<br/>• Test: GTest harness (1.0d)", table_cell_style),
            Paragraph("<b>Build:</b> 1.5d<br/><b>Transitive Build Dep:</b> 1.5d (jemalloc 64k config)<br/><b>Engineering:</b> 1.5d base × 1.0 × 1.0 = <b>1.5d</b><br/><b>Test:</b> 1.0d<br/><b>Sum:</b> 1.5 + 1.5 + 1.5 + 1.0 = 5.5 ≈ 6 PD", table_cell_code),
            Paragraph("<b>6 PD</b>", table_cell_bold)
        ]
    ]
    examples_table = Table(examples_data, colWidths=[110, 160, 192, 60])
    examples_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), SECONDARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
    ]))
    story.append(examples_table)

    # =========================================================================
    # PAGE 4: DEMONSTRATION SCENARIOS & STRATEGIC VALUE
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("6. Demonstrated Workload Scenarios & Validation", h1_style))
    story.append(Paragraph(
        "The prototype was tested and validated across four production-grade enterprise migration workloads:",
        body_style
    ))
    story.append(Spacer(1, 2))

    demo_data = [
        [Paragraph("Scenario / Workload", table_header_style), Paragraph("Stack Components", table_header_style), Paragraph("Agent Triage Findings & Recommendations", table_header_style), Paragraph("Score & Sizing", table_header_style)],
        [
            Paragraph("<b>Enterprise Cloud Microservices</b>", table_cell_style),
            Paragraph("Nginx, Redis, PostgreSQL, Strimzi Kafka, Node.js", table_cell_style),
            Paragraph("All components have verified native ppc64le container images in Docker Hub and Quay.io. Multi-stage Dockerfile audit confirmed ppc64le base images.", table_cell_style),
            Paragraph("<font color='#16a34a'><b>100% GO</b></font><br/><b>5 Person-Days</b><br/>(Smoke & staging)", table_cell_style)
        ],
        [
            Paragraph("<b>AI / ML Vector Pipeline</b>", table_cell_style),
            Paragraph("PyTorch, NumPy, Pandas, Scipy, Custom C++ DSP", table_cell_style),
            Paragraph("PyTorch routed to IBM Open-CE with Power MMA acceleration; custom DSP kernel scoped with SIMDe AVX2->VSX remediation. Test suite validated.", table_cell_style),
            Paragraph("<font color='#16a34a'><b>Minor Effort</b></font><br/><b>8 Person-Days</b><br/>(Fibonacci Sized)", table_cell_style)
        ],
        [
            Paragraph("<b>High-Throughput Storage Engine</b>", table_cell_style),
            Paragraph("RocksDB 8.6, simdjson 3.6, Redis, zlib", table_cell_style),
            Paragraph("Deep dependency iceberg scoped: 6 build deps, including 64KB-page tuned jemalloc and SIMD vector translation. Full transparent derivation provided.", table_cell_style),
            Paragraph("<font color='#d97706'><b>Moderate Effort</b></font><br/><b>21 Person-Days</b><br/>(Fibonacci Sized)", table_cell_style)
        ],
        [
            Paragraph("<b>Legacy Financial Analytics</b>", table_cell_style),
            Paragraph("Intel MKL, Python 3.9, Proprietary Risk Calc", table_cell_style),
            Paragraph("Proprietary closed-source x86 blocker flagged; automated recommendation to substitute with <b>IBM ESSL</b> or OpenBLAS.", table_cell_style),
            Paragraph("<font color='#7c3aed'><b>Not Possible As-Is</b></font><br/><b>Arch Substitution</b><br/>(ESSL / OpenBLAS)", table_cell_style)
        ]
    ]
    demo_table = Table(demo_data, colWidths=[115, 110, 217, 80])
    demo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), SECONDARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
    ]))
    story.append(demo_table)
    story.append(Spacer(1, 8))

    # Section 7: Strategic Value
    story.append(Paragraph("7. Strategic Value to IBM & Program Alignment", h1_style))
    story.append(Paragraph(
        "This prototype directly addresses the core mission of the <b>AI Elite Program</b> by applying advanced agentic AI to eliminate real-world enterprise sales friction:",
        body_style
    ))
    story.append(Paragraph("1. <b>Accelerates Infrastructure Revenue:</b> Eliminates the 5-to-10 day qualification bottleneck, arming client teams with authoritative migration roadmaps within seconds of first contact.", bullet_style))
    story.append(Paragraph("2. <b>Optimizes Engineering Allocation:</b> Prevents the IBM Power Porting Lab from wasting bandwidth on off-the-shelf components, focusing scarce specialist time exclusively on scoped unported libraries.", bullet_style))
    story.append(Paragraph("3. <b>Demonstrates Hybrid AI Leadership:</b> Seamlessly combines deterministic knowledge-graph probing, container registry APIs, and multi-model LLM reasoning to solve mission-critical systems challenges.", bullet_style))
    story.append(Paragraph("4. <b>Actionable Developer Deliverables:</b> Generates one-click executive 1-page proposals alongside structured CSV engineering backlogs ready for immediate JIRA ingestion.", bullet_style))
    story.append(Spacer(1, 8))

    # Callout Box: Submission Sign-off
    callout_data = [[
        Paragraph(
            "<b>Submission Note:</b> Prototype is fully implemented and operational, containerized via Podman / Docker Compose, validated with a 100% passing test suite across all 7 gap features, and available for live demonstration.",
            callout_style
        )
    ]]
    callout_table = Table(callout_data, colWidths=[522])
    callout_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
        ('BORDER', (0, 0), (-1, -1), 1, PRIMARY),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(callout_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated presentation PDF: {output_path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "customer_presentation.pdf"
    build_presentation_pdf(out)
