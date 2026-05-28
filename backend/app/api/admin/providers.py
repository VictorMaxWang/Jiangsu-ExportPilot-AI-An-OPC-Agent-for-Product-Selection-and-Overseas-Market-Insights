from fastapi import APIRouter, Depends

from app.schemas import ProviderStatusResponse, ProviderTestResponse
from app.schemas.provider_status import ProviderId
from app.services.provider_status import ProviderStatusService, get_provider_status_service


router = APIRouter()


@router.get("/status", response_model=ProviderStatusResponse)
def get_provider_status(
    service: ProviderStatusService = Depends(get_provider_status_service),
) -> ProviderStatusResponse:
    return service.list_status()


@router.post("/test/{provider}", response_model=ProviderTestResponse)
async def test_provider(
    provider: ProviderId,
    service: ProviderStatusService = Depends(get_provider_status_service),
) -> ProviderTestResponse:
    return await service.test_provider(provider)
