"""Typed runtime configuration.

Every setting can be supplied through an environment variable prefixed with
``SCIAGENT_`` (for example ``SCIAGENT_DATABASE_URL``). Defaults are chosen so
that the whole platform runs locally without any external service.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SCIAGENT_", env_file=".env", extra="ignore")

    env: Literal["local", "dev", "staging", "prod", "test"] = "local"
    log_level: str = "INFO"

    # Persistence
    database_url: str = "sqlite+pysqlite:///./sciagent.db"
    data_lake_uri: str = "./.lake"

    # LLM serving (vLLM exposes an OpenAI-compatible API)
    llm_backend: Literal["vllm", "rule"] = "rule"
    llm_base_url: str = "http://localhost:8001/v1"
    llm_model: str = "sciagent-llm"
    llm_timeout_s: float = 30.0
    llm_max_tokens: int = 1024

    # Tool transport: in-process registry or remote MCP servers
    tool_transport: Literal["local", "mcp"] = "local"
    mcp_imaging_url: str = "http://localhost:8101/mcp"
    mcp_genomics_url: str = "http://localhost:8102/mcp"
    mcp_clinical_url: str = "http://localhost:8103/mcp"

    # Security: comma separated "key:user:role:group1|group2" entries
    api_keys: str = Field(
        default="dev-researcher-key:alice:researcher:imaging|genomics|clinical,"
        "dev-admin-key:admin:admin:*"
    )

    # Agent behaviour
    agent_max_steps: int = 6
    embedding_dim: int = 256


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
