FROM apache/airflow:3.3.2-python3.12
COPY --chown=airflow:root pyproject.toml README.md /opt/sciagent/
COPY --chown=airflow:root src /opt/sciagent/src
RUN pip install --no-cache-dir "/opt/sciagent[postgres,s3]"
COPY --chown=airflow:root dags /opt/airflow/dags
