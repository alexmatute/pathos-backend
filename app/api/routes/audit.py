from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from typing import Optional

from app.db.database import get_db
from app.models.audit_log import AuditLog
from app.core.security import get_current_user
from app.schemas.schemas import AuditListResponse, AuditLogOut
from app.services.audit_service import get_audit_summary

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("", response_model=AuditListResponse)
async def list_audit_logs(
    action: Optional[str] = Query(None),
    user_email: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Solo admins y pathologists pueden ver el log de auditoría."""
    if current_user["role"] == "viewer":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Sin acceso al log de auditoría")

    stmt = select(AuditLog).order_by(desc(AuditLog.timestamp))
    if action: stmt = stmt.where(AuditLog.action == action)
    if user_email: stmt = stmt.where(AuditLog.user_email.ilike(f"%{user_email}%"))
    if status: stmt = stmt.where(AuditLog.status == status)

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar() or 0

    alerts_stmt = select(func.count()).select_from(AuditLog).where(AuditLog.status == "alert")
    alerts = (await db.execute(alerts_stmt)).scalar() or 0

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return AuditListResponse(items=logs, total=total, alerts=alerts)


@router.get("/summary")
async def audit_summary(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Estadísticas de auditoría para el dashboard."""
    return await get_audit_summary(db)
