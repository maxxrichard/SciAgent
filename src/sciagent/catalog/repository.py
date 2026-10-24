"""Repositories encapsulating catalog queries."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select

from sciagent.catalog.db import Database
from sciagent.catalog.models import AgentRun, Dataset
from sciagent.core.errors import NotFoundError
from sciagent.core.ids import new_id


class DatasetRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def register(
        self,
        *,
        name: str,
        modality: str,
        group: str,
        uri: str,
        row_count: int,
        checksum: str,
        schema: dict[str, Any],
        lineage: dict[str, Any] | None = None,
        description: str = "",
    ) -> Dataset:
        """Register a dataset, bumping the version when the name already exists."""
        with self.db.session() as s:
            latest = s.scalar(select(func.max(Dataset.version)).where(Dataset.name == name))
            ds = Dataset(
                id=new_id("ds"),
                name=name,
                modality=modality,
                group=group,
                uri=uri,
                version=(latest or 0) + 1,
                row_count=row_count,
                checksum=checksum,
                schema_=schema,
                lineage=lineage or {},
                description=description,
            )
            s.add(ds)
            return ds

    def get(self, dataset_id: str) -> Dataset:
        with self.db.session() as s:
            ds = s.get(Dataset, dataset_id)
            if ds is None:
                raise NotFoundError("dataset not found", dataset_id=dataset_id)
            return ds

    def list(
        self, *, groups: Iterable[str] | None = None, modality: str | None = None
    ) -> list[Dataset]:
        stmt = select(Dataset).order_by(Dataset.name, Dataset.version.desc())
        if modality:
            stmt = stmt.where(Dataset.modality == modality)
        if groups is not None and "*" not in set(groups):
            stmt = stmt.where(Dataset.group.in_(list(groups)))
        with self.db.session() as s:
            return list(s.scalars(stmt))

    def latest(self, name: str) -> Dataset:
        stmt = select(Dataset).where(Dataset.name == name).order_by(Dataset.version.desc())
        with self.db.session() as s:
            ds = s.scalars(stmt).first()
            if ds is None:
                raise NotFoundError("dataset not found", name=name)
            return ds


class RunRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(self, *, user: str, question: str, model: str) -> AgentRun:
        with self.db.session() as s:
            run = AgentRun(id=new_id("run"), user=user, question=question, model=model)
            s.add(run)
            return run

    def finish(self, run_id: str, **fields: Any) -> AgentRun:
        with self.db.session() as s:
            run = s.get(AgentRun, run_id)
            if run is None:
                raise NotFoundError("run not found", run_id=run_id)
            for key, value in fields.items():
                setattr(run, key, value)
            return run

    def get(self, run_id: str) -> AgentRun:
        with self.db.session() as s:
            run = s.get(AgentRun, run_id)
            if run is None:
                raise NotFoundError("run not found", run_id=run_id)
            return run

    def list_for(self, user: str | None, limit: int = 50) -> list[AgentRun]:
        stmt = select(AgentRun).order_by(AgentRun.created_at.desc()).limit(limit)
        if user is not None:
            stmt = stmt.where(AgentRun.user == user)
        with self.db.session() as s:
            return list(s.scalars(stmt))
