from __future__ import annotations

from fastapi import APIRouter, Query, status

from sciagent.api.deps import AdminDep, ContainerDep, PrincipalDep
from sciagent.api.schemas import DatasetIn, DatasetOut
from sciagent.core.errors import PolicyDenied

router = APIRouter(prefix="/v1/datasets", tags=["datasets"])


@router.get("", response_model=list[DatasetOut], response_model_by_alias=True)
def list_datasets(
    container: ContainerDep,
    principal: PrincipalDep,
    modality: str | None = Query(None, pattern=r"^(imaging|genomics|clinical)$"),
) -> list[object]:
    return container.datasets.list(groups=principal.groups, modality=modality)  # type: ignore[return-value]


@router.get("/{dataset_id}", response_model=DatasetOut, response_model_by_alias=True)
def get_dataset(dataset_id: str, container: ContainerDep, principal: PrincipalDep) -> object:
    ds = container.datasets.get(dataset_id)
    if not principal.in_group(ds.group):
        raise PolicyDenied("dataset belongs to another group", dataset_id=dataset_id)
    return ds


@router.post(
    "",
    response_model=DatasetOut,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
def register_dataset(body: DatasetIn, container: ContainerDep, admin: AdminDep) -> object:
    ds = container.datasets.register(
        name=body.name,
        modality=body.modality,
        group=body.group,
        uri=body.uri,
        row_count=body.row_count,
        checksum=body.checksum,
        schema=body.schema_,
        lineage=body.lineage,
        description=body.description,
    )
    container.audit.record(
        actor=admin.user,
        action="dataset.register",
        resource=ds.id,
        decision="allow",
        details={"name": ds.name, "version": ds.version},
    )
    container.refresh_index()
    return ds
