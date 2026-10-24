import numpy as np
import pytest

from sciagent.core.errors import NotFoundError, ToolExecutionError, ValidationFailed
from sciagent.tools import Tool, ToolRegistry
from sciagent.tools.clinical import kaplan_meier, logrank_test, median_survival, rolling_zscores
from sciagent.tools.imaging import label_components, otsu_threshold


def test_registry_exposes_eight_tools_across_three_servers(registry):
    assert len(registry.names()) == 8
    assert {s["server"] for s in registry.specs()} == {"imaging", "genomics", "clinical"}
    assert all("properties" in s["input_schema"] for s in registry.specs())


def test_registry_errors(registry):
    with pytest.raises(NotFoundError):
        registry.call("nope", {})
    with pytest.raises(ValidationFailed):
        registry.call("segment_cells", {"sample_id": "bad"})


def test_registry_wraps_tool_failures_and_rejects_duplicates():
    from pydantic import BaseModel

    class In(BaseModel):
        x: int

    def boom(_: In) -> dict:
        raise RuntimeError("kaput")

    reg = ToolRegistry()
    tool = Tool("boom", "fails", "imaging", In, boom)
    reg.register(tool)
    with pytest.raises(ValueError):
        reg.register(tool)
    with pytest.raises(ToolExecutionError, match="kaput"):
        reg.call("boom", {"x": 1})


def test_otsu_separates_bimodal_distribution():
    img = np.concatenate([np.full(100, 0.1), np.full(100, 0.9)])
    assert 0.1 < otsu_threshold(img) < 0.9


def test_label_components_counts_4_connected_regions():
    mask = np.array([[1, 1, 0, 0], [0, 0, 0, 1], [1, 0, 1, 1], [1, 0, 0, 0]], dtype=bool)
    labels, n = label_components(mask)
    assert n == 3
    assert labels[0, 0] == labels[0, 1] and labels[2, 2] == labels[1, 3]


def test_segmentation_is_deterministic_and_plausible(registry):
    a = registry.call("segment_cells", {"sample_id": "IMG-0007"})
    b = registry.call("segment_cells", {"sample_id": "IMG-0007"})
    assert a == b and 6 <= a["cell_count"] <= 16
    strict = registry.call("segment_cells", {"sample_id": "IMG-0007", "min_area": 400})
    assert strict["cell_count"] == 0 and strict["mean_area_px"] == 0.0


def test_image_features(registry):
    f = registry.call("extract_image_features", {"sample_id": "IMG-0001"})
    assert 0 < f["foreground_fraction"] < 0.5 and f["snr_db"] > 0


def test_variant_filters(registry):
    all_ = registry.call("annotate_variants", {"sample_id": "WGS-0001", "min_impact": "MODIFIER"})
    high = registry.call("annotate_variants", {"sample_id": "WGS-0001", "min_impact": "HIGH"})
    tp53 = registry.call("annotate_variants", {"sample_id": "WGS-0001", "genes": ["tp53"]})
    assert all_["variants_passing"] == all_["variants_considered"] == 120
    assert set(high["by_impact"]) == {"HIGH"} and high["top_high_impact"]
    assert set(tp53["by_gene"]) <= {"TP53"}


def test_expression_qc_flags_damaged_cells(registry):
    r = registry.call("expression_qc", {"sample_id": "SC-0001", "max_mito_fraction": 0.05})
    assert r["cells"] == 400 and 0 < r["cells_passing_qc"] < 400


def test_rolling_zscores_detects_spike():
    x = np.full(30, 70.0) + np.sin(np.arange(30))
    x[20] = 140
    z = rolling_zscores(x, 10)
    assert np.argmax(np.abs(z)) == 20 and z[:10].sum() == 0


def test_vital_anomalies(registry):
    r = registry.call("detect_vital_anomalies", {"patient_id": "PT-00012", "signal": "spo2"})
    assert r["hours"] == 72 and r["anomaly_count"] == len(r["anomalies"])


def test_cohort_filters(registry):
    r = registry.call(
        "build_cohort",
        {"diagnosis": "copd", "sex": "F", "min_age": 50, "max_age": 70, "limit": 5},
    )
    assert r["size"] > 0 and len(r["patient_ids"]) == 5 and r["female_fraction"] == 1.0
    empty = registry.call("build_cohort", {"min_age": 119, "max_age": 120})
    assert empty["size"] == 0 and empty["median_age"] is None


def test_kaplan_meier_matches_hand_calculation():
    t = np.array([1, 2, 3, 4, 5.0])
    e = np.array([True, True, False, True, False])
    times, surv = kaplan_meier(t, e)
    assert times.tolist() == [1, 2, 4]
    np.testing.assert_allclose(surv, [0.8, 0.6, 0.3])
    assert median_survival(times, surv) == 4
    assert median_survival(np.array([1.0]), np.array([0.9])) is None


def test_logrank_identical_groups_is_not_significant():
    t = np.arange(1, 21, dtype=float)
    e = np.ones(20, dtype=bool)
    chi2, p = logrank_test(t, e, t.copy(), e.copy())
    assert chi2 == 0 and p == 1.0
    chi2, p = logrank_test(t, e, t * 4, e)
    assert p < 0.05


def test_survival_analysis(registry):
    r = registry.call("survival_analysis", {"diagnosis": "sepsis", "compare_by": "sex"})
    assert set(r["groups"]) == {"F", "M"} and 0 <= r["logrank"]["p_value"] <= 1
    one = registry.call("survival_analysis", {"min_age": 94, "max_age": 95})
    assert "logrank" not in one or len(one["groups"]) == 2


def test_harmonise_records_tool(registry):
    r = registry.call(
        "harmonise_records",
        {
            "records": [
                {"code": "TEMP", "value": 212, "unit": "F"},
                {"code": "ZZZ", "value": 1, "unit": "x"},
            ]
        },
    )
    assert r["records"][0]["value"] == 100.0 and r["status_counts"] == {"ok": 1, "unmapped": 1}
