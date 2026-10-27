"""Run with: python tests/test_resolve.py  (or pytest)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from semantic.resolve import load_all, metric_sql, resolve, validate, week_expr  # noqa: E402

CLIENTS, METRICS, TEMPLATES = load_all()


def keys(client_id):
    return [s.key for s in resolve(client_id, CLIENTS, METRICS, TEMPLATES)[0]]


def test_shipped_config_is_valid():
    assert validate(CLIENTS, METRICS, TEMPLATES) == []


def test_labels_use_client_conversion_name():
    labels = [s.label for s in resolve("pulsefit", CLIENTS, METRICS, TEMPLATES)[0]]
    assert "Installs" in labels and "Cost per Install" in labels


def test_client_labels_rename_without_changing_math():
    # Juniper calls cost per order "CPO" and revenue / spend "ROI".
    # The labels change; the SQL is exactly the shared definition.
    slots = {s.key: s for s in resolve("juniper", CLIENTS, METRICS, TEMPLATES)[0]}
    assert slots["cpa"].label == "CPO" and slots["roas"].label == "ROI"
    assert slots["roas"].sql == metric_sql("roas", METRICS, {})
    brewbox = {s.key: s.label for s in resolve("brewbox", CLIENTS, METRICS, TEMPLATES)[0]}
    assert brewbox["sessions"] == "Visits"


def test_missing_data_hides_metric_with_reason():
    # PulseFit is an app and sends no site sessions, so sessions and
    # conversion rate drop out of its CPA template, with a reason.
    slots, hidden = resolve("pulsefit", CLIENTS, METRICS, TEMPLATES)
    assert [s.key for s in slots] == ["spend", "conversions", "cpa"]
    assert {h.key for h in hidden} == {"sessions", "cvr"}
    assert "sessions" in hidden[0].reason


def test_two_kpi_types_merge_without_duplicates():
    # Juniper watches ROAS and CPA: the ROAS template first, then whatever
    # the CPA template adds that is not already there.
    assert keys("juniper") == ["spend", "revenue", "roas", "conversions", "aov", "cpa", "sessions", "cvr"]


def test_ratios_are_ratio_of_sums():
    sql = metric_sql("cpa", METRICS, {})
    assert sql == "sum(spend) / nullif(sum(conversions), 0)"


def test_adjustment_applies_inside_the_ratio():
    sql = {s.key: s.sql for s in resolve("pulsefit", CLIENTS, METRICS, TEMPLATES)[0]}["cpa"]
    assert sql == "sum(spend) / nullif((sum(conversions) * 1.15), 0)"


def test_bad_config_is_caught():
    bad = {"x": {"kpi_types": ["cpa", "not_a_type"], "week_start": "funday",
                 "sends": ["spend", "clicks"], "labels": {"cpx": "CPX"}, "targets": {"nope": 1}}}
    errors = validate(bad, METRICS, TEMPLATES)
    assert len(errors) == 5, errors


def test_week_start_expression():
    assert "+ 7) % 7" in week_expr("monday")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
