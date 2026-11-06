from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth.dashboard_access import DashboardPrincipal, Permission
from app.core.auth.dependencies import (
    require_dashboard_permission,
    set_dashboard_error_format,
    validate_dashboard_session,
)
from app.dependencies import DashboardContext, get_dashboard_context
from app.modules.dashboard.schemas import (
    DashboardOverviewResponse,
    DashboardOverviewTimeframeKey,
    DashboardProjectionsResponse,
)

router = APIRouter(
    prefix="/api",
    tags=["dashboard"],
    dependencies=[Depends(validate_dashboard_session), Depends(set_dashboard_error_format)],
)


@router.get(
    "/dashboard/overview",
    response_model=DashboardOverviewResponse,
    dependencies=[Depends(require_dashboard_permission(Permission.ACCOUNTS_READ))],
)
async def get_overview(
    timeframe: DashboardOverviewTimeframeKey = Query("7d"),
    principal: DashboardPrincipal = Depends(validate_dashboard_session),
    context: DashboardContext = Depends(get_dashboard_context),
) -> DashboardOverviewResponse:
    return await context.service.get_overview(
        timeframe,
        redact_identity=not principal.has(Permission.ACCOUNTS_WRITE),
    )


@router.get(
    "/dashboard/projections",
    response_model=DashboardProjectionsResponse,
    dependencies=[Depends(require_dashboard_permission(Permission.ACCOUNTS_READ))],
)
async def get_projections(
    context: DashboardContext = Depends(get_dashboard_context),
) -> DashboardProjectionsResponse:
    return await context.service.get_projections()


@router.get("/models", dependencies=[Depends(require_dashboard_permission(Permission.DASHBOARD_READ))])
async def list_models(request: Request) -> dict:
    catalog = request.app.state.swissai.catalog
    return {
        "models": [
            {"id": model["id"], "name": model.get("name", model["id"]), "sourceOnly": True}
            for model in catalog.available()
        ]
    }
