"""Generate one Airflow DAG per pipeline spec in ``sciagent/data/pipelines.yaml``.

Each DAG has three tasks mirroring :func:`sciagent.data.pipelines.run_pipeline`
stages; the heavy lifting is the shared runner so Airflow stays a thin scheduler.
Tasks run in the ``sciagent/api`` image via the KubernetesExecutor, with IRSA
granting read/write to the raw and curated buckets only.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from sciagent.data.pipelines import PipelineSpec, load_specs

DEFAULT_ARGS = {
    "owner": "sciagent-data",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "execution_timeout": timedelta(hours=1),
}


def _dry_validate(pipeline_id: str) -> int:
    from sciagent.data.pipelines import EXTRACTORS, get_spec, validate

    spec = get_spec(pipeline_id)
    failures = validate(EXTRACTORS[spec.kind](spec.params), spec.checks)
    if failures:
        raise ValueError(f"{pipeline_id}: {failures}")
    return len(failures)


def _run(pipeline_id: str) -> dict[str, object]:
    from sciagent.catalog.db import Database
    from sciagent.catalog.repository import DatasetRepository
    from sciagent.core.config import get_settings
    from sciagent.data.lake import Lake
    from sciagent.data.pipelines import get_spec, run_pipeline

    settings = get_settings()
    db = Database(settings.database_url)
    result = run_pipeline(
        get_spec(pipeline_id), Lake(settings.data_lake_uri), DatasetRepository(db)
    )
    return result.__dict__


def _refresh_index() -> int:
    from sciagent.api.container import build_container
    from sciagent.core.config import get_settings

    return build_container(get_settings()).refresh_index()


def build_dag(spec: PipelineSpec) -> DAG:
    with DAG(
        dag_id=f"sciagent__{spec.id.replace('-', '_')}",
        description=spec.description,
        schedule=spec.schedule,
        start_date=datetime(2026, 1, 1),
        catchup=False,
        max_active_runs=1,
        default_args=DEFAULT_ARGS,
        tags=["sciagent", spec.modality, spec.kind],
    ) as dag:
        check = PythonOperator(
            task_id="quality_gate", python_callable=_dry_validate, op_args=[spec.id]
        )
        publish = PythonOperator(task_id="publish", python_callable=_run, op_args=[spec.id])
        index = PythonOperator(task_id="refresh_index", python_callable=_refresh_index)
        check >> publish >> index
    return dag


for _spec in load_specs():
    globals()[f"dag_{_spec.id.replace('-', '_')}"] = build_dag(_spec)
