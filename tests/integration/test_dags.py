import pytest

airflow = pytest.importorskip("airflow", reason="Airflow is an optional dependency")


def test_one_dag_per_pipeline():
    from airflow.models import DagBag

    bag = DagBag(dag_folder="dags", include_examples=False)
    assert not bag.import_errors
    assert len(bag.dags) == 40
    dag = bag.get_dag("sciagent__clinical_registry_sepsis")
    assert [t.task_id for t in dag.topological_sort()] == [
        "quality_gate",
        "publish",
        "refresh_index",
    ]
