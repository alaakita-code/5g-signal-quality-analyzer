"""
generate_report_cli.py
=========================
不依賴 Streamlit 的命令列報告產生工具,適合本機排程(cron)或
GitHub Actions 排程自動跑報告用。

使用方式:
    python scripts/generate_report_cli.py \
        --config configs/default_config.yaml \
        --output-dir reports_output \
        --format both

    # 也可以指定套用某個案例演示情境,而不是用預設模擬參數
    python scripts/generate_report_cli.py --scenario urban_congestion
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from analysis import hotspot_detection, metrics  # noqa: E402
from data_generator.scenarios import apply_scenario  # noqa: E402
from data_generator.simulate_cell_data import generate  # noqa: E402
from reports.report_generator import build_markdown_report, build_pdf_report  # noqa: E402


def run(config_path: str, output_dir: str, fmt: str, scenario_id: str | None, top_n: int) -> None:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if scenario_id:
        config = apply_scenario(config, scenario_id)
        print(f"套用案例演示情境:{scenario_id}")

    df = generate(config)
    thresholds = config["thresholds"]
    df = hotspot_detection.flag_poor_samples(
        df,
        rsrp_poor_dbm=thresholds["rsrp_poor_dbm"],
        sinr_poor_db=thresholds["sinr_poor_db"],
        load_high_pct=thresholds["load_high_pct"],
    )
    per_cell = metrics.per_cell_summary(df)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if fmt in ("markdown", "both"):
        md_text = build_markdown_report(df, per_cell, config, top_n=top_n)
        md_path = out_dir / f"signal_quality_report_{timestamp}.md"
        md_path.write_text(md_text, encoding="utf-8")
        print(f"已產生 Markdown 報告:{md_path}")

    if fmt in ("pdf", "both"):
        pdf_bytes = build_pdf_report(df, per_cell, config, top_n=top_n)
        pdf_path = out_dir / f"signal_quality_report_{timestamp}.pdf"
        pdf_path.write_bytes(pdf_bytes)
        print(f"已產生 PDF 報告:{pdf_path}")


def main():
    parser = argparse.ArgumentParser(description="不依賴 Streamlit,直接從命令列產生分析報告")
    parser.add_argument("--config", default="configs/default_config.yaml", help="設定檔路徑")
    parser.add_argument("--output-dir", default="reports_output", help="報告輸出目錄")
    parser.add_argument(
        "--format", choices=["markdown", "pdf", "both"], default="both", help="輸出格式"
    )
    parser.add_argument(
        "--scenario", default=None,
        help="套用案例演示情境的 id(見 src/data_generator/scenarios.py),不指定則用純模擬參數",
    )
    parser.add_argument("--top-n", type=int, default=5, help="報告中列出前幾名瓶頸小區")
    args = parser.parse_args()

    run(args.config, args.output_dir, args.format, args.scenario, args.top_n)


if __name__ == "__main__":
    main()
