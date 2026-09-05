"""測試 analysis.bottleneck_analysis 與 analysis.recommendations。"""

from __future__ import annotations

from analysis import bottleneck_analysis, metrics, recommendations


def test_score_bottleneck_range_and_sorted(small_df):
    per_cell = metrics.per_cell_summary(small_df)
    scored = bottleneck_analysis.score_bottleneck(per_cell)

    assert "bottleneck_score" in scored.columns
    assert scored["bottleneck_score"].between(0, 100).all()
    # 應依分數由高到低排序
    scores = scored["bottleneck_score"].tolist()
    assert scores == sorted(scores, reverse=True)


def test_top_n_bottlenecks_respects_n(small_df):
    per_cell = metrics.per_cell_summary(small_df)
    top2 = bottleneck_analysis.top_n_bottlenecks(per_cell, n=2)
    assert len(top2) == min(2, len(per_cell))


def test_generate_recommendations_adds_columns(small_df):
    per_cell = metrics.per_cell_summary(small_df)
    scored = bottleneck_analysis.score_bottleneck(per_cell)
    with_reco = recommendations.generate_recommendations(scored)

    assert "recommendations" in with_reco.columns
    assert "recommendations_text" in with_reco.columns
    # 每個小區至少要有一條建議(包含「目前正常」的預設建議)
    assert with_reco["recommendations"].apply(lambda tips: len(tips) >= 1).all()


def test_high_load_cell_gets_load_recommendation(small_df):
    per_cell = metrics.per_cell_summary(small_df)
    per_cell = per_cell.copy()
    per_cell.loc[0, "avg_load_pct"] = 95.0
    per_cell.loc[0, "max_load_pct"] = 99.0
    with_reco = recommendations.generate_recommendations(per_cell)
    assert "負載" in with_reco.loc[0, "recommendations_text"]
