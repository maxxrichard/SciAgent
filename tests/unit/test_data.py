import pytest

from sciagent.catalog.repository import DatasetRepository
from sciagent.core.errors import NotFoundError, ValidationFailed
from sciagent.data import synthetic
from sciagent.data.lake import Lake, table_checksum
from sciagent.data.pipelines import (
    EXTRACTORS,
    PipelineSpec,
    get_spec,
    load_specs,
    run_pipeline,
    validate,
)


def test_forty_pipelines_with_unique_ids_and_known_kinds():
    specs = load_specs()
    assert len(specs) == 40
    assert len({s.id for s in specs}) == 40
    assert {s.kind for s in specs} <= set(EXTRACTORS)
    assert {s.modality for s in specs} == {"imaging", "genomics", "clinical"}


def test_get_spec_unknown():
    with pytest.raises(NotFoundError):
        get_spec("nope")


def test_synthetic_generators_are_deterministic():
    assert (synthetic.microscopy_image("IMG-0001") == synthetic.microscopy_image("IMG-0001")).all()
    assert synthetic.variants("WGS-0001") == synthetic.variants("WGS-0001")
    assert synthetic.clinical_cohort(10) == synthetic.clinical_cohort(10)


def test_validate_reports_each_failure():
    rows = [{"a": 1, "b": None}, {"a": 1, "b": 5}]
    failures = validate(
        rows, {"min_rows": 3, "not_null": ["b"], "range": {"b": [0, 1]}, "unique": ["a"]}
    )
    assert len(failures) == 4
    assert validate(rows[1:], {"not_null": ["a", "b"]}) == []


@pytest.mark.parametrize("pipeline_id", [s.id for s in load_specs()])
def test_every_pipeline_passes_its_quality_checks(pipeline_id):
    spec = get_spec(pipeline_id)
    assert validate(EXTRACTORS[spec.kind](spec.params), spec.checks) == []


def test_run_pipeline_publishes_versioned_reproducible_dataset(tmp_path, db):
    repo, lake = DatasetRepository(db), Lake(str(tmp_path))
    spec = get_spec("clinical-labs-harmonised-site-a")
    r1 = run_pipeline(spec, lake, repo)
    r2 = run_pipeline(spec, lake, repo)
    assert (r1.version, r2.version) == (1, 2)
    assert r1.checksum == r2.checksum  # same inputs → same content hash
    table = lake.read(r2.uri)
    assert table.num_rows == r2.rows and table_checksum(table) == r2.checksum
    ds = repo.latest(spec.id)
    assert ds.lineage["pipeline"] == spec.id and ds.schema_["loinc"] == "string"
    assert {d.version for d in repo.list(groups=["clinical"], modality="clinical")} == {1, 2}
    assert repo.list(groups=["imaging"]) == []


def test_failed_quality_gate_raises_and_publishes_nothing(tmp_path, db):
    repo = DatasetRepository(db)
    spec = PipelineSpec(
        "bad",
        "clinical_registry",
        "clinical",
        "clinical",
        "@daily",
        {"diagnosis": "unknown"},
        {"min_rows": 1},
        "",
    )
    with pytest.raises(ValidationFailed):
        run_pipeline(spec, Lake(str(tmp_path)), repo)
    assert repo.list() == []
