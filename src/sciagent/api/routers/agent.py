from __future__ import annotations

from fastapi import APIRouter, Query

from sciagent.api.deps import ContainerDep, PrincipalDep
from sciagent.api.schemas import QueryRequest, RunOut, SearchHit
from sciagent.catalog.models import AgentRun
from sciagent.core.errors import NotFoundError, SciAgentError

router = APIRouter(prefix="/v1", tags=["agent"])


@router.post("/query", response_model=RunOut)
def query(body: QueryRequest, container: ContainerDep, principal: PrincipalDep) -> AgentRun:
    run = container.runs.create(
        user=principal.user, question=body.question, model=container.llm.model
    )
    try:
        result = container.agent.run(body.question, principal, run.id)
    except SciAgentError as exc:
        container.runs.finish(run.id, status="failed", answer=exc.message)
        raise
    return container.runs.finish(
        run.id,
        status=result.status,
        answer=result.answer,
        steps=result.steps,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        latency_s=result.latency_s,
    )


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    container: ContainerDep, principal: PrincipalDep, limit: int = Query(20, ge=1, le=200)
) -> list[AgentRun]:
    return container.runs.list_for(None if principal.is_admin else principal.user, limit)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, container: ContainerDep, principal: PrincipalDep) -> AgentRun:
    run = container.runs.get(run_id)
    if run.user != principal.user and not principal.is_admin:
        raise NotFoundError("run not found", run_id=run_id)
    return run


@router.get("/search", response_model=list[SearchHit])
def search(
    container: ContainerDep,
    principal: PrincipalDep,
    q: str = Query(..., min_length=2, max_length=500),
    k: int = Query(5, ge=1, le=20),
) -> list[SearchHit]:
    return [
        SearchHit(id=d.id, text=d.text, score=round(score, 4))
        for d, score in container.retriever.search(q, k)
    ]
