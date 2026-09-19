import io
import datetime
from typing import Dict, Any, List
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Canvas that dynamically computes total page numbers for running headers and footers."""
    header_subtitle = "Pre-Sales Executive Qualification Memo"

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

        # Header (on pages > 1)
        if self._pageNumber > 1:
            self.drawString(45, 752, f"IBM Power Porting Triage Agent — {self.header_subtitle}")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(45, 746, 567, 746)

        # Footer (on all pages)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(45, 42, 567, 42)

        footer_text = "CONFIDENTIAL — FOR CLIENT TECHNICAL QUALIFICATION & ARCHITECTURE REVIEW"
        self.drawString(45, 30, footer_text)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(567, 30, page_str)
        self.restoreState()


class ExecutivePDFGenerator:
    """Generates an executive-ready, polished PDF qualification memo from triage results."""

    @classmethod
    def generate(cls, triage_data: Dict[str, Any]) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=45,
            rightMargin=45,
            topMargin=46,
            bottomMargin=46
        )

        styles = getSampleStyleSheet()

        # Modern Executive Palette
        PRIMARY = colors.HexColor("#0f62fe")        # IBM Blue
        SECONDARY = colors.HexColor("#002d9c")      # Cobalt
        TEXT_DARK = colors.HexColor("#0f172a")      # Slate 900
        TEXT_MUTED = colors.HexColor("#475569")     # Slate 600
        BG_LIGHT = colors.HexColor("#f8fafc")       # Slate 50
        BG_ALT = colors.HexColor("#f1f5f9")         # Slate 100
        BORDER_COLOR = colors.HexColor("#cbd5e1")   # Slate 300
        ACCENT_EMERALD = colors.HexColor("#059669") # Emerald Green
        ACCENT_CYAN = colors.HexColor("#0284c7")    # Cyan Blue
        ACCENT_AMBER = colors.HexColor("#d97706")   # Amber Warning
        ACCENT_ROSE = colors.HexColor("#e11d48")    # Rose Red

        title_style = ParagraphStyle(
            'DocTitle', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=18, leading=22,
            textColor=SECONDARY, spaceAfter=2
        )
        subtitle_style = ParagraphStyle(
            'DocSubtitle', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=10, leading=13,
            textColor=PRIMARY, spaceAfter=8
        )
        h1_style = ParagraphStyle(
            'SectionH1', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=13, leading=17,
            textColor=SECONDARY, spaceBefore=10, spaceAfter=4,
            keepWithNext=True
        )
        h2_style = ParagraphStyle(
            'SectionH2', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=10, leading=13,
            textColor=TEXT_DARK, spaceBefore=6, spaceAfter=3,
            keepWithNext=True
        )
        body_style = ParagraphStyle(
            'Body', parent=styles['Normal'],
            fontName='Helvetica', fontSize=8.5, leading=11.5,
            textColor=TEXT_DARK, spaceAfter=4
        )
        body_muted = ParagraphStyle(
            'BodyMuted', parent=styles['Normal'],
            fontName='Helvetica', fontSize=8, leading=11,
            textColor=TEXT_MUTED
        )
        callout_style = ParagraphStyle(
            'Callout', parent=styles['Normal'],
            fontName='Helvetica-Oblique', fontSize=8.5, leading=12,
            textColor=TEXT_DARK
        )

        # Ensure uncompressed stream for instant inspection & fast rendering
        import reportlab.rl_config
        reportlab.rl_config.pageCompression = 0

        project_name = triage_data.get("project_name", "Workload Migration")
        target_os = triage_data.get("target_os", "RHEL9")
        target_platform = triage_data.get("target_platform", "OPENSHIFT")
        summary = triage_data.get("summary", {})
        packages = triage_data.get("packages", [])

        # Primary package & provenance details
        primary_pkg = triage_data.get("primary_package_name")
        if not primary_pkg and packages:
            primary_pkg = packages[0].get("package_name")
        if not primary_pkg:
            for cand in ["rocksdb", "redis", "nginx", "fastapi", "pytorch", "torch", "simdjson"]:
                if cand in project_name.lower():
                    primary_pkg = cand
                    break

        git_repo_url = triage_data.get("git_repo_url")
        doc_url = triage_data.get("doc_url")
        source_url = triage_data.get("source_url") or git_repo_url or doc_url

        # Well-known fallback enrichment for known packages if not already present
        if primary_pkg:
            pkg_lower = primary_pkg.lower()
            if "rocksdb" in pkg_lower:
                git_repo_url = git_repo_url or "https://github.com/facebook/rocksdb"
                doc_url = doc_url or "https://rocksdb.org"
            elif "redis" in pkg_lower:
                git_repo_url = git_repo_url or "https://github.com/redis/redis"
                doc_url = doc_url or "https://redis.io"
            elif "nginx" in pkg_lower:
                git_repo_url = git_repo_url or "https://github.com/nginx/nginx"
                doc_url = doc_url or "https://nginx.org"
            elif "fastapi" in pkg_lower:
                git_repo_url = git_repo_url or "https://github.com/tiangolo/fastapi"
                doc_url = doc_url or "https://fastapi.tiangolo.com"
            elif "pytorch" in pkg_lower or "torch" in pkg_lower:
                git_repo_url = git_repo_url or "https://github.com/pytorch/pytorch"
                doc_url = doc_url or "https://pytorch.org"
            elif "simdjson" in pkg_lower:
                git_repo_url = git_repo_url or "https://github.com/simdjson/simdjson"
                doc_url = doc_url or "https://simdjson.org"

        pkg_version = triage_data.get("package_version")
        if not pkg_version and packages:
            pkg_version = packages[0].get("requested_version", "latest")
        if not pkg_version:
            pkg_version = "latest"

        pkg_ecosystem = triage_data.get("package_ecosystem")
        if not pkg_ecosystem and packages:
            pkg_ecosystem = packages[0].get("ecosystem", "native_c")
        if not pkg_ecosystem:
            pkg_ecosystem = "native_c"

        # Configure dynamic running header for pages > 1
        has_custom_project = project_name and project_name not in ["Customer Migration Triage", "Migration_Triage", "Workload Migration", "Report"]
        if has_custom_project:
            NumberedCanvas.header_subtitle = f"Porting Qualification: {project_name}"
            doc_heading = f"Executive Porting Qualification: {project_name}"
        elif primary_pkg:
            NumberedCanvas.header_subtitle = f"Porting Qualification: {primary_pkg}"
            doc_heading = f"Executive Porting Qualification: {primary_pkg}"
        else:
            NumberedCanvas.header_subtitle = f"Qualification: {project_name}"
            doc_heading = f"Executive Qualification Memo: {project_name}"

        # Fibonacci Effort
        fib_effort = summary.get("fibonacci_effort_pd", 0)
        if not fib_effort:
            fib_effort = summary.get("max_total_person_days", 5)

        readiness_pct = summary.get("readiness_score_pct", 0.0)
        rec = summary.get("recommendation", "Minor Effort")
        rec_reason = summary.get("recommendation_reason", "")

        story = []

        # Document Header
        story.append(Paragraph("IBM Power Porting Triage Agent — AI Pre-Sales Qualification", subtitle_style))
        story.append(Paragraph(doc_heading, title_style))
        
        meta_items = [
            f"<b>Target Architecture:</b> IBM Power (ppc64le)",
            f"<b>Target OS:</b> {target_os} on {target_platform}",
            f"<b>Date:</b> {datetime.date.today().strftime('%B %d, %Y')}"
        ]
        if primary_pkg:
            meta_items.insert(0, f"<b>Primary Component:</b> {primary_pkg} ({pkg_version})")
        elif project_name and has_custom_project:
            meta_items.insert(0, f"<b>Project:</b> {project_name}")

        story.append(Paragraph(" | ".join(meta_items), body_muted))
        story.append(Spacer(1, 4))
        story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY, spaceAfter=8))

        # Workload Provenance & Source Specification Card
        git_link_p = f"<a href='{git_repo_url}'><font color='#002d9c'><u>{git_repo_url}</u></font></a>" if git_repo_url else "<font color='#64748b'>Not specified</font>"
        doc_link_p = f"<a href='{doc_url}'><font color='#002d9c'><u>{doc_url}</u></font></a>" if doc_url else "<font color='#64748b'>Not specified</font>"
        
        source_label = "GitHub Repository Manifest Ingestion" if git_repo_url and "github" in (source_url or "") else (
            "Documentation Website Analysis" if doc_url and "http" in (source_url or "") else "Application Manifest / Free-Form Notes"
        )

        provenance_data = [
            [
                Paragraph(f"<b>Target Component:</b> <font color='{SECONDARY.hexval()}'><b>{primary_pkg or 'General Workload'}</b></font> (Version: <code>{pkg_version}</code>)", body_style),
                Paragraph(f"<b>Ecosystem / Runtime:</b> <b>{pkg_ecosystem.upper()}</b>", body_style),
            ],
            [
                Paragraph(f"<b>GitHub Repository:</b> {git_link_p}", body_style),
                Paragraph(f"<b>Documentation Link:</b> {doc_link_p}", body_style),
            ],
            [
                Paragraph(f"<b>Ingestion Origin:</b> {source_label}", body_style),
                Paragraph(f"<b>Target Platform:</b> IBM Power (ppc64le) | {target_os}", body_style),
            ]
        ]
        t_provenance = Table(provenance_data, colWidths=[261, 261])
        t_provenance.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f0fdf4")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#86efac")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#bbf7d0")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 4.5),
        ]))
        story.append(t_provenance)
        story.append(Spacer(1, 8))

        # Section 1: Executive Feasibility Scorecard
        story.append(Paragraph("1. Executive Feasibility Scorecard & Qualification", h1_style))
        
        # Color coding for recommendation
        rec_color = ACCENT_EMERALD if "Minimal" in rec else (
            ACCENT_CYAN if "Minor" in rec else (
                ACCENT_AMBER if "Moderate" in rec else colors.HexColor("#7c3aed")
            )
        )

        scorecard_data = [
            [
                Paragraph("<b>Porting Readiness Score</b>", body_style),
                Paragraph(f"<b><font color='{ACCENT_EMERALD.hexval()}'>{readiness_pct}%</font></b>", body_style),
                Paragraph("<b>Sales Recommendation Tier</b>", body_style),
                Paragraph(f"<b><font color='{rec_color.hexval()}'>{rec}</font></b>", body_style),
            ],
            [
                Paragraph("<b>Fibonacci Effort Estimate</b>", body_style),
                Paragraph(f"<b><font color='{PRIMARY.hexval()}'>{fib_effort} Person-Days</font></b>", body_style),
                Paragraph("<b>Analyzed Components</b>", body_style),
                Paragraph(f"{summary.get('total_packages', len(packages))} ({summary.get('native_count', 0)} Native, {summary.get('substitute_count', 0)} Sub, {summary.get('unported_count', 0)} Unported)", body_style),
            ],
            [
                Paragraph("<b>Transitive Build Requirements</b>", body_style),
                Paragraph(f"{summary.get('unported_transitive_deps_count', 0)} unported build-time deps", body_style),
                Paragraph("<b>Test Suites Unresolved</b>", body_style),
                Paragraph(f"{summary.get('test_deps_unresolved_count', 0)} harness requirements", body_style),
            ]
        ]

        t_scorecard = Table(scorecard_data, colWidths=[140, 120, 140, 122])
        t_scorecard.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), BG_LIGHT),
            ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t_scorecard)
        story.append(Spacer(1, 6))

        # Strategic Rationale Callout
        callout_data = [[
            Paragraph(f"<b>Strategic Qualification Rationale:</b> {rec_reason}", callout_style)
        ]]
        t_callout = Table(callout_data, colWidths=[522])
        t_callout.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#93c5fd")),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t_callout)
        story.append(Spacer(1, 10))

        # Section 2: IBM Power Hardware Value Proposition
        story.append(Paragraph("2. Strategic Value of Migrating to IBM Power (ppc64le)", h1_style))
        value_prop_p = Paragraph(
            "Migrating this workload to IBM Power delivers enterprise-class performance advantages: "
            "<b>Industry-leading memory bandwidth</b> to eliminate data starvation in transactional and time-series pipelines, "
            "<b>SMT8 hardware multi-threading</b> (up to 8 simultaneous execution threads per core) for dense cloud container consolidation, "
            "and <b>transparent Open-CE & enterprise Linux support</b> ensuring optimized acceleration and mission-critical reliability.",
            body_style
        )
        story.append(value_prop_p)
        story.append(Spacer(1, 8))

        # Section 3: Dependency Readiness & Sizing Matrix Table
        story.append(Paragraph("3. Component Readiness & Porting Sizing Matrix", h1_style))

        table_header = [
            Paragraph("<b>Component</b>", body_style),
            Paragraph("<b>Ecosystem</b>", body_style),
            Paragraph("<b>Readiness Status</b>", body_style),
            Paragraph("<b>Build System</b>", body_style),
            Paragraph("<b>Transitive Deps</b>", body_style),
            Paragraph("<b>Effort (PD)</b>", body_style),
        ]
        table_rows = [table_header]

        for p in packages:
            status_str = p.get("status", "")
            if status_str == "native_available":
                status_cell = f"<font color='{ACCENT_EMERALD.hexval()}'>Native ppc64le</font>"
            elif status_str == "platform_agnostic":
                status_cell = f"<font color='{PRIMARY.hexval()}'>Platform Agnostic</font>"
            elif status_str == "substitute_available":
                status_cell = f"<font color='#7c3aed'>Substitute Exists</font>"
            elif status_str == "unported_build_required":
                status_cell = f"<font color='{ACCENT_AMBER.hexval()}'>Source Build Req</font>"
            else:
                status_cell = f"<font color='{ACCENT_ROSE.hexval()}'>Alternative Req</font>"

            build_sys = p.get("build_system") or "Binary"
            num_deps = len(p.get("build_dependencies", []))
            trans_str = f"{num_deps} scoped" if num_deps > 0 else "0"
            effort_str = f"{p.get('total_effort_pd', 0)} PD" if p.get('total_effort_pd', 0) > 0 else "Ready"

            # Check if package has repository/doc links
            p_name = p.get("package_name", "")
            p_ver = p.get("requested_version", "latest")
            comp_content = f"<b>{p_name}</b><br/><font size='7' color='#64748b'>{p_ver}</font>"
            
            p_url = p.get("git_repo_url") or p.get("doc_url") or p.get("evidence_url")
            if not p_url and primary_pkg and p_name.lower() == primary_pkg.lower():
                p_url = git_repo_url or doc_url
            if p_url:
                short_url = p_url.replace("https://", "").replace("http://", "")
                if len(short_url) > 26:
                    short_url = short_url[:24] + "..."
                comp_content += f"<br/><font size='6' color='#002d9c'><a href='{p_url}'><u>{short_url}</u></a></font>"

            table_rows.append([
                Paragraph(comp_content, body_style),
                Paragraph(p.get("ecosystem", "container"), body_style),
                Paragraph(status_cell, body_style),
                Paragraph(build_sys, body_style),
                Paragraph(trans_str, body_style),
                Paragraph(effort_str, body_style),
            ])

        t_matrix = Table(table_rows, colWidths=[130, 75, 105, 80, 72, 60])
        t_matrix.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BG_ALT),
            ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_matrix)
        story.append(Spacer(1, 10))

        # Section 4: Architecture Sensitivity & Remediation Audit
        unported_pkgs = [p for p in packages if p.get("status") == "unported_build_required"]
        if unported_pkgs:
            story.append(Paragraph("4. Architecture Sensitivity Audit & Engineering Remediations", h1_style))
            for p in unported_pkgs:
                pkg_name = p.get("package_name")
                arch = p.get("arch_sensitivity") or {}
                has_simd = arch.get("has_simd_avx")
                has_page = arch.get("has_64k_page_risk")
                has_asm = arch.get("has_inline_asm")
                remedy = arch.get("remediation_strategy") or "Standard gcc/clang rebuild on ppc64le."

                detail_p = Paragraph(
                    f"<b>{pkg_name}</b> — Total Effort: {p.get('total_effort_pd', 0)} PD<br/>"
                    f"• <b>SIMD Instructions:</b> {arch.get('simd_instruction_count', 0)} (Tier: {arch.get('simd_porting_complexity', 'DIRECT')})<br/>"
                    f"• <b>64KB Page Sensitivity:</b> {'Yes (allocator tuning required)' if has_page else 'Standard'}<br/>"
                    f"• <b>Inline Assembly:</b> {'Yes (yield/pause markers)' if has_asm else 'None'}<br/>"
                    f"• <b>Prescribed Remediation:</b> {remedy}",
                    body_style
                )
                story.append(detail_p)
                story.append(Spacer(1, 4))

        # Section 5: Technical Sales Handoff
        story.append(Spacer(1, 6))
        story.append(Paragraph("5. Recommended Pre-Sales Next Steps", h1_style))
        target_name = primary_pkg or project_name
        next_steps = (
            f"1. <b>Present Qualification Memo:</b> Share this assessment with client enterprise architecture leadership.<br/>"
            f"2. <b>Porting Lab Handoff:</b> Submit scoped <b>{target_name}</b> transitive build requirements to the IBM Power Porting Lab for source staging.<br/>"
            f"3. <b>Leverage Open-CE:</b> Deploy accelerated AI runtime packages via IBM Open-CE channels on Red Hat OpenShift on Power."
        )
        story.append(Paragraph(next_steps, body_style))

        # Build document
        doc.build(story, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        return buffer.getvalue()
