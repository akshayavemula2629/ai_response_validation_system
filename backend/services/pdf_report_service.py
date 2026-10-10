"""
Publication-Grade PDF Report Generation Service for AI Response Validation System.
Generates multi-page vector PDF reports for Batch Evaluations and Single Evaluations using ReportLab.
"""
import io
import logging
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

COLOR_PRIMARY = colors.HexColor("#1E293B")      # Slate 800
COLOR_SECONDARY = colors.HexColor("#0284C7")    # Sky 600
COLOR_ACCENT = colors.HexColor("#0F172A")       # Slate 900
COLOR_PASS = colors.HexColor("#10B981")         # Emerald 500
COLOR_WARN = colors.HexColor("#F59E0B")         # Amber 500
COLOR_FAIL = colors.HexColor("#EF4444")         # Red 500
COLOR_BG_LIGHT = colors.HexColor("#F8FAFC")     # Slate 50
COLOR_BORDER = colors.HexColor("#E2E8F0")       # Slate 200
COLOR_TEXT_MUTED = colors.HexColor("#64748B")   # Slate 500


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and draw total page numbers and running headers/footers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, total_pages):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(COLOR_TEXT_MUTED)

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 36, "AI Response Validation System | Evaluation Audit Report")
            self.setStrokeColor(COLOR_BORDER)
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Running Footer (all pages)
        self.setStrokeColor(COLOR_BORDER)
        self.setLineWidth(0.5)
        self.line(54, 48, letter[0] - 54, 48)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        self.drawString(54, 34, f"Generated: {now_str} | Confidential - Internal Quality Benchmark")
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(letter[0] - 54, 34, page_str)
        self.restoreState()


def get_report_styles():
    """Generates custom typography styles for ReportLab flowables."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="DocTitle",
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=COLOR_PRIMARY,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name="DocSubtitle",
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=COLOR_SECONDARY,
        spaceAfter=14
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=COLOR_PRIMARY,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name="SubsectionHeader",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=COLOR_SECONDARY,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        name="TableHead",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.white,
        alignment=0
    ))
    styles.add(ParagraphStyle(
        name="TableCell",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=COLOR_PRIMARY
    ))
    styles.add(ParagraphStyle(
        name="TableCellBold",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=COLOR_PRIMARY
    ))
    styles.add(ParagraphStyle(
        name="TableCellMuted",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=COLOR_TEXT_MUTED
    ))
    styles.add(ParagraphStyle(
        name="MetaLabel",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=COLOR_TEXT_MUTED
    ))
    styles.add(ParagraphStyle(
        name="MetaValue",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=COLOR_PRIMARY
    ))
    return styles


def generate_batch_pdf_report(summary: Dict[str, Any], results: List[Dict[str, Any]]) -> bytes:
    """Generates a publication-grade multi-page Executive PDF Report for a batch run."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    styles = get_report_styles()
    story = []

    # Title & Header
    story.append(Paragraph("AI Response Validation System", styles["DocTitle"]))
    batch_id = summary.get("batch_id", "BATCH-EVAL")
    dataset_name = summary.get("dataset_name", "batch.csv")
    story.append(Paragraph(f"Executive Evaluation Report & Audit Breakdown | {dataset_name}", styles["DocSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_SECONDARY, spaceAfter=12))

    # Metadata Grid
    eval_time = summary.get("evaluation_time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    total_eval = summary.get("actually_evaluated") or summary.get("total_records") or len(results)
    file_total = summary.get("file_total") or summary.get("total_records") or len(results)

    meta_data = [
        [
            Paragraph("Batch Run ID:", styles["MetaLabel"]),
            Paragraph(str(batch_id), styles["MetaValue"]),
            Paragraph("Evaluation Date:", styles["MetaLabel"]),
            Paragraph(str(eval_time), styles["MetaValue"])
        ],
        [
            Paragraph("Dataset Source:", styles["MetaLabel"]),
            Paragraph(str(dataset_name), styles["MetaValue"]),
            Paragraph("Records Evaluated:", styles["MetaLabel"]),
            Paragraph(f"{total_eval} of {file_total} total records", styles["MetaValue"])
        ]
    ]
    meta_table = Table(meta_data, colWidths=[100, 160, 100, 144])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
        ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # Executive Summary KPI Block
    story.append(Paragraph("1. Executive Quality & Compliance Summary", styles["SectionHeader"]))

    pass_rate = summary.get("pass_rate", 0.0)
    needs_imp_rate = summary.get("needs_improvement_rate", 0.0)
    fail_rate = summary.get("fail_rate", 0.0)
    avg_score = summary.get("average_score", summary.get("average_overall", 0.0))
    hal_freq = summary.get("hallucination_frequency", 0.0)

    v_counts = summary.get("verdict_counts", {})
    pass_cnt = v_counts.get("PASS", 0)
    ni_cnt = v_counts.get("NEEDS IMPROVEMENT", 0)
    fail_cnt = v_counts.get("FAIL", 0)

    kpi_data = [
        [
            Paragraph("Metric", styles["TableHead"]),
            Paragraph("Count", styles["TableHead"]),
            Paragraph("Rate / Score", styles["TableHead"]),
            Paragraph("Assessment", styles["TableHead"])
        ],
        [
            Paragraph("Pass Verdict", styles["TableCellBold"]),
            Paragraph(str(pass_cnt), styles["TableCell"]),
            Paragraph(f"{pass_rate}%", styles["TableCellBold"]),
            Paragraph("Production Ready", styles["TableCellMuted"])
        ],
        [
            Paragraph("Needs Improvement", styles["TableCellBold"]),
            Paragraph(str(ni_cnt), styles["TableCell"]),
            Paragraph(f"{needs_imp_rate}%", styles["TableCellBold"]),
            Paragraph("Minor Omissions / Ambiguities", styles["TableCellMuted"])
        ],
        [
            Paragraph("Fail Verdict", styles["TableCellBold"]),
            Paragraph(str(fail_cnt), styles["TableCell"]),
            Paragraph(f"{fail_rate}%", styles["TableCellBold"]),
            Paragraph("Factual Error / Contradiction", styles["TableCellMuted"])
        ],
        [
            Paragraph("Overall Quality Score", styles["TableCellBold"]),
            Paragraph("-", styles["TableCell"]),
            Paragraph(f"{avg_score} / 100", styles["TableCellBold"]),
            Paragraph("Weighted Multi-Agent Composite", styles["TableCellMuted"])
        ],
        [
            Paragraph("Hallucination Frequency", styles["TableCellBold"]),
            Paragraph("-", styles["TableCell"]),
            Paragraph(f"{hal_freq}%", styles["TableCellBold"]),
            Paragraph("Responses with unsupported claims", styles["TableCellMuted"])
        ]
    ]

    kpi_table = Table(kpi_data, colWidths=[140, 70, 100, 194])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 14))

    # Dimension Performance Breakdown
    story.append(Paragraph("2. Multi-Agent Dimensional Performance", styles["SectionHeader"]))

    dim_data = [
        [
            Paragraph("Evaluation Dimension", styles["TableHead"]),
            Paragraph("Weight", styles["TableHead"]),
            Paragraph("Average Score", styles["TableHead"]),
            Paragraph("Evaluation Focus", styles["TableHead"])
        ],
        [
            Paragraph("Query Relevance", styles["TableCellBold"]),
            Paragraph("25%", styles["TableCell"]),
            Paragraph(f"{summary.get('average_relevance', 0.0)} / 100", styles["TableCellBold"]),
            Paragraph("Direct alignment with query intent and constraints", styles["TableCellMuted"])
        ],
        [
            Paragraph("Factual Accuracy", styles["TableCellBold"]),
            Paragraph("30%", styles["TableCell"]),
            Paragraph(f"{summary.get('average_accuracy', 0.0)} / 100", styles["TableCellBold"]),
            Paragraph("Grounding consistency against reference ground truth", styles["TableCellMuted"])
        ],
        [
            Paragraph("Completeness & Coverage", styles["TableCellBold"]),
            Paragraph("25%", styles["TableCell"]),
            Paragraph(f"{summary.get('average_completeness', 0.0)} / 100", styles["TableCellBold"]),
            Paragraph("Exhaustiveness across all required subquestions", styles["TableCellMuted"])
        ],
        [
            Paragraph("Hallucination Safety", styles["TableCellBold"]),
            Paragraph("20%", styles["TableCell"]),
            Paragraph(f"{summary.get('average_hallucination', 0.0)} / 100", styles["TableCellBold"]),
            Paragraph("Freedom from fabricated, speculative, or unverified claims", styles["TableCellMuted"])
        ]
    ]

    dim_table = Table(dim_data, colWidths=[130, 60, 100, 214])
    dim_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_SECONDARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(dim_table)
    story.append(Spacer(1, 14))

    # Common Failure Modes & Diagnostics
    rec_issues = summary.get("recurring_issues", [])
    if rec_issues:
        story.append(Paragraph("3. Common Evaluation Failure Modes", styles["SectionHeader"]))
        issue_rows = [
            [
                Paragraph("Detected Quality Issue", styles["TableHead"]),
                Paragraph("Category", styles["TableHead"]),
                Paragraph("Count", styles["TableHead"]),
                Paragraph("Impact %", styles["TableHead"]),
                Paragraph("Severity", styles["TableHead"])
            ]
        ]
        for iss in rec_issues[:5]:
            issue_rows.append([
                Paragraph(str(iss.get("issue", "")), styles["TableCellBold"]),
                Paragraph(str(iss.get("category", "")), styles["TableCell"]),
                Paragraph(str(iss.get("count", 0)), styles["TableCell"]),
                Paragraph(f"{iss.get('percentage', 0.0)}%", styles["TableCellBold"]),
                Paragraph(str(iss.get("severity", "Medium")), styles["TableCellMuted"])
            ])

        issue_table = Table(issue_rows, colWidths=[174, 110, 60, 80, 80])
        issue_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
            ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(issue_table)
        story.append(Spacer(1, 14))

    # Detailed Records Table
    story.append(PageBreak())
    story.append(Paragraph("4. Individual Evaluated Records Breakdown", styles["SectionHeader"]))
    story.append(Paragraph(
        "Complete itemized audit log of evaluated records showing dimensional scores, overall score, and final verdict.",
        styles["TableCellMuted"]
    ))
    story.append(Spacer(1, 8))

    rec_headers = [
        Paragraph("Row", styles["TableHead"]),
        Paragraph("Question & AI Response", styles["TableHead"]),
        Paragraph("Rel", styles["TableHead"]),
        Paragraph("Acc", styles["TableHead"]),
        Paragraph("Hal", styles["TableHead"]),
        Paragraph("Comp", styles["TableHead"]),
        Paragraph("Score", styles["TableHead"]),
        Paragraph("Verdict", styles["TableHead"])
    ]

    rec_rows = [rec_headers]
    for r in results:
        q_txt = str(r.get("question", ""))[:80] + ("..." if len(str(r.get("question", ""))) > 80 else "")
        ai_txt = str(r.get("ai_response", ""))[:95] + ("..." if len(str(r.get("ai_response", ""))) > 95 else "")
        q_cell = Paragraph(f"<b>Q:</b> {q_txt}<br/><b>A:</b> {ai_txt}", styles["TableCell"])

        row_id = str(r.get("row_id") or r.get("row_index") or "-")
        rel_sc = f"{float(r.get('relevance_score') or 0.0):.0f}"
        acc_sc = f"{float(r.get('accuracy_score') or 0.0):.0f}"
        hal_sc = f"{float(r.get('hallucination_score') or 0.0):.0f}"
        comp_sc = f"{float(r.get('completeness_score') or 0.0):.0f}"
        ovr_sc = f"{float(r.get('overall_score') or 0.0):.1f}"
        verd = str(r.get("final_verdict") or r.get("verdict") or "FAIL")

        rec_rows.append([
            Paragraph(row_id, styles["TableCellBold"]),
            q_cell,
            Paragraph(rel_sc, styles["TableCell"]),
            Paragraph(acc_sc, styles["TableCell"]),
            Paragraph(hal_sc, styles["TableCell"]),
            Paragraph(comp_sc, styles["TableCell"]),
            Paragraph(ovr_sc, styles["TableCellBold"]),
            Paragraph(verd, styles["TableCellBold"])
        ])

    rec_table = Table(rec_rows, colWidths=[30, 244, 32, 32, 32, 36, 44, 54], repeatRows=1)
    rec_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(rec_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()


def generate_single_pdf_report(eval_data: Dict[str, Any]) -> bytes:
    """Generates a comprehensive publication-grade forensic PDF report for a single evaluation."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    styles = get_report_styles()
    story = []

    # Title & Header
    story.append(Paragraph("AI Response Validation System", styles["DocTitle"]))
    req_id = eval_data.get("request_id") or eval_data.get("evaluation_id") or "SINGLE-EVAL"
    story.append(Paragraph(f"Forensic Single Evaluation Audit Report | {req_id}", styles["DocSubtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=COLOR_SECONDARY, spaceAfter=12))

    # Metadata & Verdict Summary
    timestamp = eval_data.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    overall_score = float(eval_data.get("overall_score") or 0.0)
    verdict = (
        eval_data.get("verdict_result", {}).get("final_verdict") or
        eval_data.get("final_verdict") or
        eval_data.get("verdict") or
        "FAIL"
    )

    meta_data = [
        [
            Paragraph("Evaluation ID:", styles["MetaLabel"]),
            Paragraph(str(req_id), styles["MetaValue"]),
            Paragraph("Timestamp:", styles["MetaLabel"]),
            Paragraph(str(timestamp), styles["MetaValue"])
        ],
        [
            Paragraph("Overall Verdict:", styles["MetaLabel"]),
            Paragraph(f"<b>{verdict}</b>", styles["MetaValue"]),
            Paragraph("Overall Score:", styles["MetaLabel"]),
            Paragraph(f"<b>{overall_score:.1f} / 100</b>", styles["MetaValue"])
        ]
    ]
    meta_table = Table(meta_data, colWidths=[100, 160, 100, 144])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_BG_LIGHT),
        ('BOX', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # Evaluated Input & AI Response
    story.append(Paragraph("1. Evaluated Prompt & Response Artifacts", styles["SectionHeader"]))

    q_text = eval_data.get("question", "")
    resp_text = eval_data.get("ai_response") or eval_data.get("original_response") or ""
    ref_text = eval_data.get("reference_ground_truth") or eval_data.get("reference_answer") or ""

    artifacts_data = [
        [Paragraph("User Question", styles["TableHead"]), Paragraph(q_text, styles["TableCellBold"])],
        [Paragraph("Candidate AI Response", styles["TableHead"]), Paragraph(resp_text, styles["TableCell"])],
        [Paragraph("Reference Ground Truth", styles["TableHead"]), Paragraph(ref_text if ref_text else "(None provided - KB retrieval evaluated)", styles["TableCell"])]
    ]
    artifacts_table = Table(artifacts_data, colWidths=[140, 364])
    artifacts_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), COLOR_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(artifacts_table)
    story.append(Spacer(1, 14))

    # Dimension Score Breakdown
    story.append(Paragraph("2. Multi-Agent Dimensional Analysis", styles["SectionHeader"]))

    rel_res = eval_data.get("relevance_result") or eval_data.get("relevance_judge") or {}
    acc_res = eval_data.get("accuracy_result") or eval_data.get("accuracy_judge") or {}
    hal_res = eval_data.get("hallucination_result") or eval_data.get("hallucination_judge") or {}
    comp_res = eval_data.get("completeness_result") or eval_data.get("completeness_judge") or {}

    rel_sc = rel_res.get("score") or rel_res.get("score_normalized") or eval_data.get("relevance_score") or 0.0
    acc_sc = acc_res.get("score") or acc_res.get("score_normalized") or eval_data.get("accuracy_score") or 0.0
    hal_sc = hal_res.get("score") or (100.0 - float(hal_res.get("hallucination_percentage", 0.0))) if hal_res else 100.0
    comp_sc = comp_res.get("score") or comp_res.get("completeness_score") or eval_data.get("completeness_score") or 0.0

    dim_data = [
        [
            Paragraph("Dimension", styles["TableHead"]),
            Paragraph("Weight", styles["TableHead"]),
            Paragraph("Score", styles["TableHead"]),
            Paragraph("Agent Assessment & Reasoning", styles["TableHead"])
        ],
        [
            Paragraph("Relevance", styles["TableCellBold"]),
            Paragraph("25%", styles["TableCell"]),
            Paragraph(f"{float(rel_sc):.1f} / 100", styles["TableCellBold"]),
            Paragraph(str(rel_res.get("reasoning") or rel_res.get("explanation") or "Evaluated against intent."), styles["TableCell"])
        ],
        [
            Paragraph("Accuracy", styles["TableCellBold"]),
            Paragraph("30%", styles["TableCell"]),
            Paragraph(f"{float(acc_sc):.1f} / 100", styles["TableCellBold"]),
            Paragraph(str(acc_res.get("reasoning") or acc_res.get("explanation") or "Grounded factual consistency."), styles["TableCell"])
        ],
        [
            Paragraph("Completeness", styles["TableCellBold"]),
            Paragraph("25%", styles["TableCell"]),
            Paragraph(f"{float(comp_sc):.1f} / 100", styles["TableCellBold"]),
            Paragraph(str(comp_res.get("reasoning") or "Evaluated requirements coverage."), styles["TableCell"])
        ],
        [
            Paragraph("Hallucination Safety", styles["TableCellBold"]),
            Paragraph("20%", styles["TableCell"]),
            Paragraph(f"{float(hal_sc):.1f} / 100", styles["TableCellBold"]),
            Paragraph(str(hal_res.get("explanation") or "Evaluated claim groundings."), styles["TableCell"])
        ]
    ]

    dim_table = Table(dim_data, colWidths=[110, 50, 74, 270])
    dim_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_SECONDARY),
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(dim_table)
    story.append(Spacer(1, 14))

    # Atomic Claims Breakdown
    claims = hal_res.get("claims_breakdown") or []
    if claims:
        story.append(Paragraph("3. Atomic Claim Verification Audit", styles["SectionHeader"]))
        claim_rows = [
            [
                Paragraph("Extracted Claim", styles["TableHead"]),
                Paragraph("Classification", styles["TableHead"]),
                Paragraph("Grounding Evidence / Rationale", styles["TableHead"])
            ]
        ]
        for c in claims:
            status_style = styles["TableCellBold"]
            claim_rows.append([
                Paragraph(str(c.get("claim", "")), styles["TableCell"]),
                Paragraph(str(c.get("status", "")), status_style),
                Paragraph(str(c.get("evidence") or c.get("explanation") or ""), styles["TableCellMuted"])
            ])

        claim_table = Table(claim_rows, colWidths=[180, 94, 230])
        claim_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_PRIMARY),
            ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(claim_table)
        story.append(Spacer(1, 14))

    # Better Answer Recommendation
    better_answer = eval_data.get("better_answer")
    if better_answer:
        story.append(Paragraph("4. Recommended Grounded Answer", styles["SectionHeader"]))
        rec_data = [
            [Paragraph("Synthesis Rationale", styles["TableHead"]), Paragraph(str(eval_data.get("better_answer_reason", "Recommended grounded correction.")), styles["TableCellMuted"])],
            [Paragraph("Optimized Answer", styles["TableHead"]), Paragraph(str(better_answer), styles["TableCellBold"])]
        ]
        rec_table = Table(rec_data, colWidths=[140, 364])
        rec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), COLOR_SECONDARY),
            ('GRID', (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(rec_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
