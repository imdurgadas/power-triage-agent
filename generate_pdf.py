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
            self.drawString(54, 750, "IBM Power Porting Triage Agent — AI Elite Program Submission")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(54, 744, 558, 744)

        # Footer
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)
        
        footer_text = "CONFIDENTIAL — FOR INTERNAL REVIEW & PROGRAM SUBMISSION ONLY"
        self.drawString(54, 32, footer_text)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_str)
        self.restoreState()


def build_presentation_pdf(output_path="customer_presentation.pdf"):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom Color Palette
    PRIMARY = colors.HexColor("#0f62fe")      # IBM Blue
    SECONDARY = colors.HexColor("#002d9c")    # Dark Cobalt
    TEXT_DARK = colors.HexColor("#0f172a")    # Slate 900
    TEXT_MUTED = colors.HexColor("#475569")   # Slate 600
    BG_LIGHT = colors.HexColor("#f8fafc")     # Light background
    BORDER_COLOR = colors.HexColor("#cbd5e1") # Border grey
    ACCENT_GREEN = colors.HexColor("#16a34a") # Green
    ACCENT_AMBER = colors.HexColor("#d97706") # Amber

    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=SECONDARY,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=PRIMARY,
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=SECONDARY,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=PRIMARY,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=TEXT_DARK,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'BulletText',
        parent=body_style,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=4
    )

    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        leading=14,
        textColor=SECONDARY
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=TEXT_DARK
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=table_cell_style,
        fontName='Helvetica-Bold'
    )

    story = []

    # Title Block
    story.append(Paragraph("AI Elite Program — Customer Presentation Document", title_style))
    story.append(Paragraph("Autonomous IBM Power Porting Triage Agent", subtitle_style))
    
    meta_data = [
        [
            Paragraph("<b>Initiative:</b> AI Elite Program Prototype Submission", table_cell_style),
            Paragraph("<b>Target Architecture:</b> IBM Power (ppc64le)", table_cell_style)
        ],
        [
            Paragraph("<b>Persona:</b> Technical Pre-Sales & Migration Specialists", table_cell_style),
            Paragraph("<b>Runtime Platforms:</b> RHEL 8/9, OpenShift (OCP), Ubuntu, SLES", table_cell_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[250, 254])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # Section 1: Customer & Persona
    story.append(Paragraph("1. Customer & Target Persona", h1_style))
    story.append(Paragraph(
        "<b>Customer Profile:</b> Global enterprises running high-throughput transactional, time-series, and data/AI workloads (banking, telecom, retail, and healthcare) evaluating migration from commodity x86 infrastructure to <b>IBM Power (ppc64le)</b> on Red Hat Enterprise Linux and OpenShift.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Target Personas:</b>",
        body_style
    ))
    story.append(Paragraph("• <b>IBM Technical Pre-Sales Engineers & Solution Architects:</b> Frontline technical sellers who must rapidly qualify migration feasibility, size porting timelines, and build customer confidence during competitive evaluations.", bullet_style))
    story.append(Paragraph("• <b>Enterprise Architecture Decision-Makers (CIO / VP Infrastructure):</b> Stakeholders requiring risk transparency, timeline estimates, and platform ROI before signing migration contracts.", bullet_style))
    story.append(Paragraph("• <b>IBM Power Porting Lab & Ecosystem Engineers:</b> Specialized engineering squads responsible for compiling, tuning, and verifying unported packages.", bullet_style))
    story.append(Spacer(1, 10))

    # Section 2: Business Problem
    story.append(Paragraph("2. Business Problem & Estimation Gap", h1_style))
    story.append(Paragraph(
        "While IBM Power offers unmatched hardware throughput (high memory bandwidth, SMT8 core threading, and hardware-accelerated Matrix Math Accelerators), <b>pre-sales qualification creates severe friction in the sales pipeline:</b>",
        body_style
    ))
    story.append(Paragraph("• <b>Unstandardized & Heterogeneous Inputs:</b> Customers provide dependency specifications in fragmented formats: CycloneDX/SPDX SBOM JSONs, multi-stage Dockerfiles, Python requirements.txt, or unstructured meeting notes.", bullet_style))
    story.append(Paragraph("• <b>Fragmented Ecosystem Registries:</b> Determining package availability requires tedious manual searches across RHEL BaseOS/AppStream, EPEL 9, Quay.io, Docker Hub, PyPI, and community channels (Conda-forge, IBM Open-CE).", bullet_style))
    story.append(Paragraph("• <b>The 'Iceberg' Estimation Gap:</b> When a component lacks a ready binary, pre-sales teams cannot easily see beneath the surface. Uncovered build-time dependencies (e.g. jemalloc needing 64KB page size tuning) or unported x86 SIMD intrinsics (AVX2/AVX-512) surface late, resulting in costly project overruns.", bullet_style))
    story.append(Spacer(1, 10))

    # Section 3: Business Impact Table
    story.append(Paragraph("3. Quantified Business Impact", h1_style))
    impact_data = [
        [Paragraph("Operational Dimension", table_header_style), Paragraph("Current Manual Process", table_header_style), Paragraph("AI Agent Prototype Impact", table_header_style)],
        [
            Paragraph("<b>Qualification Turnaround Time</b>", table_cell_style),
            Paragraph("5 to 10 Business Days of email exchanges & manual catalog lookups", table_cell_style),
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
            Paragraph("<b>Standardized 3-Pillar Sizing Formula</b> scoping hardware friction & build trees", table_cell_bold)
        ],
        [
            Paragraph("<b>Executive Proposal Deliverables</b>", table_cell_style),
            Paragraph("Days spent assembling custom slide decks and proposal memos", table_cell_style),
            Paragraph("<b>1-Click Executive Memo & CSV Backlog</b> generated autonomously", table_cell_bold)
        ]
    ]
    impact_table = Table(impact_data, colWidths=[130, 184, 190])
    impact_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), SECONDARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
    ]))
    story.append(impact_table)
    story.append(Spacer(1, 14))

    # Page Break for clean multi-page presentation layout
    story.append(PageBreak())

    # Section 4: Proposed Opportunity & Agentic Solution
    story.append(Paragraph("4. Proposed Opportunity: Autonomous AI Agent Architecture", h1_style))
    story.append(Paragraph(
        "We developed a production-ready, containerized AI agent combining deterministic ecosystem probing with generative sales synthesis:",
        body_style
    ))
    
    features = [
        ("Universal Manifest Ingestion Engine", "Automatically parses CycloneDX/SPDX SBOMs, Dockerfiles, Python requirements, and raw text into normalized component representations across Containers, C/C++, PyPI, RPM, and Java."),
        ("Multi-Source Deterministic Prober", "Executes real-time live queries against Quay.io, Docker Hub v2, RHEL/EPEL 9 repos, and PyPI to verify multi-arch ppc64le support, returning canonical, clickable verification URLs."),
        ("Transitive Dependency Iceberg Scoper", "Recursively analyzes unported packages to uncover hidden build-time requirements (BuildRequires, compiler toolchains, submodules)."),
        ("Hardware Architecture Sensitivity Audit", "Detects x86 SIMD/AVX2 intrinsics (prescribing SIMDe to Power VSX translations), 64KB page size sensitivities (jemalloc tuning), and inline assembly."),
        ("Standardized 3-Pillar Sizing Formula", "Computes Person-Days as Base Compilation + Transitive Sub-deps + Architecture Friction, incorporating a 1-week deployment validation baseline."),
        ("Generative Executive Proposal Engine", "Uses Google Gemini (with resilient multi-model fallback across gemini-3.5-flash and gemini-3.5-flash-lite) to draft client-ready strategic value proposals highlighting Power hardware advantages.")
    ]

    for title, desc in features:
        story.append(Paragraph(f"• <b>{title}:</b> {desc}", bullet_style))
    story.append(Spacer(1, 10))

    # Section 5: Demonstration Scenarios
    story.append(Paragraph("5. Demonstrated Workload Scenarios & Validation", h1_style))
    demo_data = [
        [Paragraph("Scenario / Workload", table_header_style), Paragraph("Stack Components", table_header_style), Paragraph("Agent Triage Findings", table_header_style), Paragraph("Score & Sizing", table_header_style)],
        [
            Paragraph("<b>Enterprise Cloud Microservices</b>", table_cell_style),
            Paragraph("Nginx, Redis, PostgreSQL, Strimzi Kafka, Node.js", table_cell_style),
            Paragraph("All components have verified native ppc64le container images in Docker Hub and Quay.io.", table_cell_style),
            Paragraph("<font color='#16a34a'><b>100% GO</b></font><br/>5 Person-Days", table_cell_style)
        ],
        [
            Paragraph("<b>AI / ML Vector Pipeline</b>", table_cell_style),
            Paragraph("PyTorch, NumPy, Pandas, Scipy, Custom C++ DSP", table_cell_style),
            Paragraph("PyTorch routed to IBM Open-CE with Power MMA acceleration; custom DSP kernel scoped with SIMDe AVX2->VSX fix.", table_cell_style),
            Paragraph("<font color='#16a34a'><b>95% GO</b></font><br/>5 – 8 Person-Days", table_cell_style)
        ],
        [
            Paragraph("<b>High-Throughput Storage Engine</b>", table_cell_style),
            Paragraph("RocksDB 8.6, simdjson 3.6, Redis, zlib", table_cell_style),
            Paragraph("Deep dependency iceberg scoped: 6 build deps uncovered, including unported 64KB-page tuned jemalloc and AVX-512 kernel.", table_cell_style),
            Paragraph("<font color='#d97706'><b>30% CAUTION</b></font><br/>8 – 12 Person-Days", table_cell_style)
        ],
        [
            Paragraph("<b>Legacy Financial Analytics</b>", table_cell_style),
            Paragraph("Intel MKL, Python 3.9, Proprietary Risk Calc", table_cell_style),
            Paragraph("Proprietary closed-source x86 blocker flagged; automated recommendation to substitute with IBM ESSL or OpenBLAS.", table_cell_style),
            Paragraph("<font color='#dc2626'><b>HIGH RISK</b></font><br/>Arch substitution", table_cell_style)
        ]
    ]
    demo_table = Table(demo_data, colWidths=[120, 110, 194, 80])
    demo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), SECONDARY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
    ]))
    story.append(demo_table)
    story.append(Spacer(1, 12))

    # Section 6: Strategic Value to IBM
    story.append(Paragraph("6. Strategic Value & Program Alignment", h1_style))
    story.append(Paragraph(
        "This prototype directly addresses the core mission of the <b>AI Elite Program</b> by applying advanced agentic AI to eliminate real-world enterprise sales friction:",
        body_style
    ))
    story.append(Paragraph("1. <b>Accelerates Infrastructure Revenue:</b> Eliminates the 10-day pre-sales bottleneck, arming client teams with authoritative migration roadmaps within seconds of first contact.", bullet_style))
    story.append(Paragraph("2. <b>Optimizes Engineering Allocation:</b> Prevents the IBM Power Porting Lab from wasting bandwidth on off-the-shelf components, focusing scarce specialist time exclusively on scoped unported libraries.", bullet_style))
    story.append(Paragraph("3. <b>Demonstrates Hybrid AI Leadership:</b> Seamlessly combines deterministic knowledge-graph probing, container registry APIs, and multi-model LLM reasoning to solve mission-critical systems challenges.", bullet_style))
    story.append(Spacer(1, 14))

    # Callout Box: Submission Sign-off
    callout_data = [[
        Paragraph(
            "<b>Submission Note:</b> Prototype is fully implemented, containerized via Podman/Docker Compose, tested with 100% passing test suites, and available for live demonstration.",
            callout_style
        )
    ]]
    callout_table = Table(callout_data, colWidths=[504])
    callout_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
        ('BORDER', (0, 0), (-1, -1), 1, PRIMARY),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(callout_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated presentation PDF: {output_path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "customer_presentation.pdf"
    build_presentation_pdf(out)
