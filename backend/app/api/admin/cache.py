from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DataSourceCache
from app.schemas import DataSourceCacheClearResponse


router = APIRouter()


@router.post("/clear", response_model=DataSourceCacheClearResponse)
def clear_all_admin_cache(db: Session = Depends(get_db)) -> DataSourceCacheClearResponse:
    return _clear_data_source_cache(db, provider=None)


@router.post("/clear/{provider}", response_model=DataSourceCacheClearResponse)
def clear_provider_data_source_cache(
    provider: str = PathParam(..., min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> DataSourceCacheClearResponse:
    return _clear_data_source_cache(db, provider=_normalize_provider(provider))


def _clear_data_source_cache(db: Session, *, provider: str | None) -> DataSourceCacheClearResponse:
    filters = []
    if provider is not None:
        filters.append(DataSourceCache.provider == provider)

    count_statement = select(func.count()).select_from(DataSourceCache)
    delete_statement = delete(DataSourceCache)
    if filters:
        count_statement = count_statement.where(*filters)
        delete_statement = delete_statement.where(*filters)

    try:
        data_source_count = int(db.scalar(count_statement) or 0)
        db.execute(delete_statement)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "DATA_SOURCE_CACHE_CLEAR_FAILED",
                "message": "Failed to clear data source cache.",
            },
        ) from exc

    return DataSourceCacheClearResponse(provider=provider, cleared_count=data_source_count)


def _normalize_provider(provider: str) -> str:
    return "_".join(provider.strip().lower().split())
