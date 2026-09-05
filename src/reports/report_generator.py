"""
report_generator.py
======================
產生分析報告,支援兩種格式:
    - Markdown(build_markdown_report):輕量、適合直接嵌入 GitHub README 或網頁
    - PDF(build_pdf_report):使用 reportlab 產生,適合正式交付/列印

報告內容包含:
    - 資料範圍與時間
    - 整體統計
    - Top 瓶頸小區與建議清單
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from analysis import bottleneck_analysis, metrics, recommendations

# 註冊隨專案附帶的繁體中文子集字型(assets/fonts/NotoSansCJKtc-Subset.ttf)。
#
# 為什麼不用 reportlab 內建的 CID 字型(如 MSung-Light)?
# 因為那些內建 CID 字型「不會把字型檔案嵌入 PDF」,而是假設開啟 PDF 的軟體
# 本身要有對應的中文字型可用——但多數瀏覽器內建的 PDF 檢視器(如 Chrome/Edge 的
# PDF.js)並沒有內建這套字,結果中文字全部顯示成空心方塊。
#
# 這裡改用「真正嵌入 PDF」的 TrueType 字型,只抽取報告會用到的字元子集
# (從 Noto Sans CJK TC 抽取,約 90KB,而非完整字型的近 20MB),
# 確保不管用哪套 PDF 檢視器打開,中文都能正確顯示。
#
# 注意:若未來在 recommendations.py 或本檔案新增了子集裡沒有的中文字,
# 該字仍會顯示不出來,需要重新執行字型子集抽取(見專案 README 說明)。
_FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
_CJK_FONT_NAME = "WenQuanYiZenHei-Subset"
_CJK_FONT_PATH = _FONT_DIR / "WenQuanYiZenHei-Subset.ttf"

if _CJK_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont(_CJK_FONT_NAME, str(_CJK_FONT_PATH)))


def _build_bottleneck_chart(top_bottlenecks: pd.DataFrame) -> Drawing:
    """用 reportlab 內建繪圖元件畫一個瓶頸分數長條圖,不需要 matplotlib 或
    任何外部圖片產生流程,純向量繪製直接嵌入 PDF。
    """
    drawing = Drawing(420, 200)

    chart = VerticalBarChart()
    chart.x = 50
    chart.y = 30
    chart.width = 340
    chart.height = 140
    chart.data = [list(top_bottlenecks["bottleneck_score"])]
    chart.categoryAxis.categoryNames = list(top_bottlenecks["cell_id"])
    chart.categoryAxis.labels.fontName = _CJK_FONT_NAME
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.angle = 0
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 100
    chart.valueAxis.labels.fontName = _CJK_FONT_NAME
    chart.valueAxis.labels.fontSize = 7
    chart.bars[0].fillColor = colors.HexColor("#2563eb")
    chart.barWidth = 12

    title = String(
        50,
        180,
        "瓶頸分數長條圖(分數越高越優先處理)",
        fontName=_CJK_FONT_NAME,
        fontSize=9,
        fillColor=colors.HexColor("#1e293b"),
    )

    drawing.add(chart)
    drawing.add(title)
    return drawing


def build_markdown_report(
    df: pd.DataFrame, per_cell_df: pd.DataFrame, config: dict, top_n: int = 5
) -> str:
    summary = metrics.overall_summary(df)
    scored = bottleneck_analysis.score_bottleneck(per_cell_df)
    with_reco = recommendations.generate_recommendations(scored)
    top_bottlenecks = with_reco.head(top_n)

    lines: list[str] = []
    lines.append("# 5G/4G 訊號品質分析報告")
    lines.append("")
    lines.append(f"報告產生時間:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## 資料範圍")
    lines.append(f"- 時間範圍:{summary['time_range'][0]} ~ {summary['time_range'][1]}")
    lines.append(f"- 小區總數:{summary['total_cells']}")
    lines.append(f"- 樣本總數:{summary['total_samples']}")
    lines.append("")
    lines.append("## 整體統計")
    lines.append(f"- 平均 RSRP:{summary['avg_rsrp_dbm']} dBm")
    lines.append(f"- 平均 RSRQ:{summary['avg_rsrq_db']} dB")
    lines.append(f"- 平均 SINR:{summary['avg_sinr_db']} dB")
    lines.append(f"- 平均負載:{summary['avg_load_pct']} %")
    lines.append("")
    lines.append(f"## Top {top_n} 瓶頸小區")
    lines.append("")
    lines.append("| 小區 | 瓶頸分數 | 平均 RSRP | 平均 SINR | 平均負載 |")
    lines.append("|---|---|---|---|---|")
    for _, row in top_bottlenecks.iterrows():
        lines.append(
            f"| {row['cell_id']} | {row['bottleneck_score']} | "
            f"{row['avg_rsrp_dbm']} dBm | {row['avg_sinr_db']} dB | {row['avg_load_pct']} % |"
        )
    lines.append("")
    lines.append("## 建議清單")
    for _, row in top_bottlenecks.iterrows():
        lines.append(f"### {row['cell_id']}")
        for tip in row["recommendations"]:
            lines.append(f"- {tip}")
        lines.append("")

    lines.append("---")
    lines.append(
        "> 本報告內容基於**模擬資料**產生,僅供功能展示與教學用途,"
        "實際網路優化決策仍須以真實路測/OSS 資料為準。"
    )

    return "\n".join(lines)


def build_pdf_report(
    df: pd.DataFrame, per_cell_df: pd.DataFrame, config: dict, top_n: int = 5
) -> bytes:
    """產生 PDF 格式的分析報告,回傳 PDF 檔案的原始 bytes。

    設計為明亮、簡潔的版面(白底黑字 + 單一主色標題),
    不使用暗色系或高對比霓虹配色。
    """
    summary = metrics.overall_summary(df)
    scored = bottleneck_analysis.score_bottleneck(per_cell_df)
    with_reco = recommendations.generate_recommendations(scored)
    top_bottlenecks = with_reco.head(top_n)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        textColor=colors.HexColor("#2563eb"),
        fontSize=20,
        fontName=_CJK_FONT_NAME,
    )
    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=12,
        spaceAfter=6,
        fontName=_CJK_FONT_NAME,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontName=_CJK_FONT_NAME,
    )
    note_style = ParagraphStyle(
        "ReportNote",
        parent=styles["BodyText"],
        textColor=colors.HexColor("#64748b"),
        fontSize=9,
        fontName=_CJK_FONT_NAME,
    )

    story = []
    story.append(Paragraph("5G/4G 訊號品質分析報告", title_style))
    story.append(
        Paragraph(
            f"報告產生時間:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body_style
        )
    )
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("資料範圍", heading_style))
    story.append(
        Paragraph(
            f"時間範圍:{summary['time_range'][0]} ~ {summary['time_range'][1]}<br/>"
            f"小區總數:{summary['total_cells']}　｜　樣本總數:{summary['total_samples']}",
            body_style,
        )
    )

    story.append(Paragraph("整體統計", heading_style))
    story.append(
        Paragraph(
            f"平均 RSRP:{summary['avg_rsrp_dbm']} dBm　｜　"
            f"平均 RSRQ:{summary['avg_rsrq_db']} dB　｜　"
            f"平均 SINR:{summary['avg_sinr_db']} dB　｜　"
            f"平均負載:{summary['avg_load_pct']} %",
            body_style,
        )
    )

    story.append(Paragraph(f"Top {top_n} 瓶頸小區", heading_style))
    table_data = [["小區", "瓶頸分數", "平均 RSRP", "平均 SINR", "平均負載"]]
    for _, row in top_bottlenecks.iterrows():
        table_data.append(
            [
                row["cell_id"],
                str(row["bottleneck_score"]),
                f"{row['avg_rsrp_dbm']} dBm",
                f"{row['avg_sinr_db']} dB",
                f"{row['avg_load_pct']} %",
            ]
        )

    table = Table(table_data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), _CJK_FONT_NAME),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eff6ff")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.5 * cm))

    if len(top_bottlenecks) > 0:
        story.append(_build_bottleneck_chart(top_bottlenecks))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("建議清單", heading_style))
    for _, row in top_bottlenecks.iterrows():
        story.append(Paragraph(f"<b>{row['cell_id']}</b>", body_style))
        for tip in row["recommendations"]:
            story.append(Paragraph(f"・{tip}", body_style))
        story.append(Spacer(1, 0.2 * cm))

    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            "本報告內容基於模擬資料產生,僅供功能展示與教學用途,"
            "實際網路優化決策仍須以真實路測/OSS 資料為準。",
            note_style,
        )
    )

    doc.build(story)
    return buffer.getvalue()

