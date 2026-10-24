from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from sciagent.agent import LocalToolGateway, SciAgent
from sciagent.api.container import Container, build_container
from sciagent.api.main import create_app
from sciagent.catalog.db import Database
from sciagent.core.config import Settings
from sciagent.core.security import Principal
from sciagent.governance.audit import AuditLog
from sciagent.governance.policy import PolicyEngine
from sciagent.llm.rule_based import RuleBasedLLM
from sciagent.tools import ToolRegistry, default_registry

RESEARCHER_KEY = "test-researcher"
IMAGING_ONLY_KEY = "test-imaging"
ADMIN_KEY = "test-admin"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        env="test",
        database_url="sqlite+pysqlite:///:memory:",
        data_lake_uri=str(tmp_path / "lake"),
        api_keys=(
            f"{RESEARCHER_KEY}:alice:researcher:imaging|genomics|clinical,"
            f"{IMAGING_ONLY_KEY}:bob:researcher:imaging,"
            f"{ADMIN_KEY}:root:admin:*"
        ),
    )


@pytest.fixture
def db() -> Database:
    database = Database("sqlite+pysqlite:///:memory:")
    database.create_all()
    return database


@pytest.fixture(scope="session")
def registry() -> ToolRegistry:
    return default_registry()


@pytest.fixture
def audit(db: Database) -> AuditLog:
    return AuditLog(db)


@pytest.fixture
def policy() -> PolicyEngine:
    return PolicyEngine.from_file()


@pytest.fixture
def agent(registry: ToolRegistry, policy: PolicyEngine, audit: AuditLog) -> SciAgent:
    return SciAgent(
        llm=RuleBasedLLM(), gateway=LocalToolGateway(registry), policy=policy, audit=audit
    )


@pytest.fixture
def alice() -> Principal:
    return Principal("alice", "researcher", frozenset({"imaging", "genomics", "clinical"}))


@pytest.fixture
def bob() -> Principal:
    return Principal("bob", "researcher", frozenset({"imaging"}))


@pytest.fixture
def admin() -> Principal:
    return Principal("root", "admin", frozenset({"*"}))


@pytest.fixture
def container(settings: Settings) -> Container:
    return build_container(settings)


@pytest.fixture
def client(settings: Settings, container: Container) -> Iterator[TestClient]:
    app = create_app(settings, container=container)
    with TestClient(app) as c:
        yield c


def auth(key: str) -> dict[str, str]:
    return {"x-api-key": key}
