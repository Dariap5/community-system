from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_secret
from app.db.models import Funnel, FunnelStep


templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/admin/{secret}", dependencies=[Depends(verify_secret)])


def _ctx(request: Request, secret: str, **extra: object) -> dict[str, object]:
    return {
        "request": request,
        "secret": secret,
        "api_base": f"/api/{secret}",
        "assets_version": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "page_data": {"secret": secret, **extra},
        **extra,
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, secret: str) -> RedirectResponse:
    return RedirectResponse(url=f"/admin/{secret}/funnels")


@router.get("/funnels", response_class=HTMLResponse)
async def funnels_list(request: Request, secret: str) -> HTMLResponse:
    return templates.TemplateResponse(request, "admin/funnels_list.html", _ctx(request, secret))


@router.get("/funnels/{funnel_id}", response_class=HTMLResponse)
async def funnel_edit(request: Request, secret: str, funnel_id: UUID, db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    funnel = await db.get(Funnel, funnel_id)
    if funnel is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Funnel not found"})

    return templates.TemplateResponse(
        request,
        "admin/funnel_edit.html",
        _ctx(request, secret, funnel_id=str(funnel_id), funnel_name=funnel.name),
    )


@router.get("/funnels/{funnel_id}/steps/{step_id}", response_class=HTMLResponse)
async def step_edit(
    request: Request,
    secret: str,
    funnel_id: UUID,
    step_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    step = await db.get(FunnelStep, step_id)
    if step is None or step.funnel_id != funnel_id:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Step not found"})

    return templates.TemplateResponse(
        request,
        "admin/step_edit.html",
        _ctx(request, secret, funnel_id=str(funnel_id), step_id=str(step_id), step_name=step.name),
    )


@router.get("/users", response_class=HTMLResponse)
async def users_list(request: Request, secret: str) -> HTMLResponse:
    return templates.TemplateResponse(request, "admin/users.html", _ctx(request, secret))


@router.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request, secret: str) -> HTMLResponse:
    return templates.TemplateResponse(request, "admin/analytics.html", _ctx(request, secret))