# Adding a pipeline

1. If the source is new, add an extractor to `EXTRACTORS` in
   `src/sciagent/data/pipelines.py` returning a list of row dicts.
2. Declare the pipeline in `src/sciagent/data/pipelines.yaml` with an `id`, `kind`,
   `modality`, `group`, cron `schedule`, `params` and quality `checks`.
3. Run it locally: `sciagent pipelines run <id>`.
4. The Airflow DAG `sciagent__<id>` is generated automatically on the next scheduler parse.

The test suite asserts that every declared pipeline passes its own quality checks.
