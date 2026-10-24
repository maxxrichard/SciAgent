# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel --wheel-dir /wheels ".[s3]"

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --uid 10001 --create-home sciagent
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
USER 10001
WORKDIR /home/sciagent
# Server name and port are supplied by the orchestrator, e.g.
#   python -m sciagent.mcp_servers imaging --port 8101
ENTRYPOINT ["python", "-m", "sciagent.mcp_servers"]
CMD ["imaging", "--transport", "streamable-http", "--port", "8101"]
