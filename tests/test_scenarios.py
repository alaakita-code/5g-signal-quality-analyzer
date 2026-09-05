"""測試 data_generator.scenarios 的情境套用邏輯。"""

from __future__ import annotations

import pytest

from data_generator.scenarios import SCENARIOS, apply_scenario, get_scenario


def test_all_scenarios_have_required_fields():
    for s in SCENARIOS:
        assert set(["id", "icon", "name", "tag", "narrative", "overrides"]).issubset(s.keys())
        assert isinstance(s["overrides"], dict)


def test_scenario_ids_are_unique():
    ids = [s["id"] for s in SCENARIOS]
    assert len(ids) == len(set(ids))


def test_get_scenario_found_and_not_found(small_config):
    s = get_scenario("urban_congestion")
    assert s["id"] == "urban_congestion"
    with pytest.raises(KeyError):
        get_scenario("not_a_real_scenario")


def test_apply_scenario_does_not_mutate_base_config(small_config):
    import copy

    original = copy.deepcopy(small_config)
    apply_scenario(small_config, "urban_congestion")
    assert small_config == original


def test_apply_scenario_overrides_take_effect(small_config):
    config = apply_scenario(small_config, "urban_congestion")
    overrides = get_scenario("urban_congestion")["overrides"]
    for key, value in overrides.items():
        assert config["simulation"][key] == value
    assert config["_scenario"]["id"] == "urban_congestion"


def test_default_scenario_has_no_overrides(small_config):
    config = apply_scenario(small_config, "default")
    assert config["simulation"] == small_config["simulation"]
