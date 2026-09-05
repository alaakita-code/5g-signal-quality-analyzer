"""測試 reports.report_generator 的 Markdown 與 PDF 產生功能。"""

from __future__ import annotations

from analysis import metrics
from reports.report_generator import build_markdown_report, build_pdf_report


def test_build_markdown_report_contains_key_sections(small_df, small_config):
    per_cell = metrics.per_cell_summary(small_df)
    report = build_markdown_report(small_df, per_cell, small_config, top_n=2)

    assert isinstance(report, str)
    assert "# 5G/4G 訊號品質分析報告" in report
    assert "## 資料範圍" in report
    assert "## 整體統計" in report
    assert "## 建議清單" in report


def test_build_markdown_report_row_count_respects_top_n(small_df, small_config):
    per_cell = metrics.per_cell_summary(small_df)
    top_n = min(2, len(per_cell))
    report = build_markdown_report(small_df, per_cell, small_config, top_n=top_n)

    # 表格內應恰有 top_n 筆資料列(不含表頭與分隔線)
    table_rows = [
        line
        for line in report.split("\n")
        if line.startswith("| CELL_")
    ]
    assert len(table_rows) == top_n


def test_build_pdf_report_returns_valid_pdf_bytes(small_df, small_config):
    per_cell = metrics.per_cell_summary(small_df)
    pdf_bytes = build_pdf_report(small_df, per_cell, small_config, top_n=2)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    # PDF 檔案的標準檔頭簽章
    assert pdf_bytes[:5] == b"%PDF-"
