"""Application container: wires settings into long-lived service objects."""

from __future__ import annotations

from dataclasses import dataclass

from sciagent.agent import LocalToolGateway, McpToolGateway, SciAgent, ToolGateway
from sciagent.catalog.db import Database
from sciagent.catalog.repository import DatasetRepository, RunRepository
from sciagent.core.config import Settings
from sciagent.core.security import ApiKeyAuthenticator
from sciagent.governance.audit import AuditLog
from sciagent.governance.policy import PolicyEngine
from sciagent.llm import LLMClient, build_llm
from sciagent.retrieval import Document, HashingEmbedder, InMemoryVectorStore
from sciagent.tools import ToolRegistry, default_registry


@dataclass
class Container:
    settings: Settings
    db: Database
    datasets: DatasetRepository
    runs: RunRepository
    audit: AuditLog
    policy: PolicyEngine
    registry: ToolRegistry
    gateway: ToolGateway
    llm: LLMClient
    retriever: InMemoryVectorStore
    auth: ApiKeyAuthenticator
    agent: SciAgent

    def refresh_index(self) -> int:
        """Re-embed tool docs and dataset descriptions for retrieval."""
        docs = [
            Document(f"tool:{s['name']}", f"Tool {s['name']} ({s['server']}): {s['description']}")
            for s in self.registry.specs()
        ]
        docs += [
            Document(
                f"dataset:{d.id}",
                f"Dataset {d.name} v{d.version} ({d.modality}, group {d.group}): {d.description}",
                {"uri": d.uri},
            )
            for d in self.datasets.list()
        ]
        self.retriever.upsert(docs)
        return len(docs)


def build_container(settings: Settings) -> Container:
    db = Database(settings.database_url)
    db.create_all()
    registry = default_registry()
    gateway: ToolGateway
    if settings.tool_transport == "mcp":
        gateway = McpToolGateway(
            registry,
            {
                "imaging": settings.mcp_imaging_url,
                "genomics": settings.mcp_genomics_url,
                "clinical": settings.mcp_clinical_url,
            },
        )
    else:
        gateway = LocalToolGateway(registry)
    audit = AuditLog(db)
    policy = PolicyEngine.from_file()
    llm = build_llm(settings)
    retriever = InMemoryVectorStore(HashingEmbedder(settings.embedding_dim))
    container = Container(
        settings=settings,
        db=db,
        datasets=DatasetRepository(db),
        runs=RunRepository(db),
        audit=audit,
        policy=policy,
        registry=registry,
        gateway=gateway,
        llm=llm,
        retriever=retriever,
        auth=ApiKeyAuthenticator(settings.api_keys),
        agent=SciAgent(
            llm=llm,
            gateway=gateway,
            policy=policy,
            audit=audit,
            retriever=retriever,
            max_steps=settings.agent_max_steps,
        ),
    )
    container.refresh_index()
    return container
