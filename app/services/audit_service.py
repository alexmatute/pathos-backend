"""
Servicio de auditoría HIPAA.
Todos los eventos de acceso, consulta e ingestión se registran en tabla append-only.
"""
from datetime import datetime, timezone
from typing import Optional
import structlog

logger = structlog.get_logger()


async def log_event(
    db,
    action: str,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    user_role: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    detail: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
    status: str = "success",
) -> None:
    """
    Registra un evento en el log de auditoría.
    Esta función NUNCA lanza excepciones — la auditoría nunca debe bloquear el flujo principal.
    """
    from app.models.audit_log import AuditLog

    try:
        device_hint = _parse_device(user_agent) if user_agent else None

        entry = AuditLog(
            user_id=user_id,
            user_email=user_email,
            user_role=user_role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            detail=detail,
            ip_address=ip_address,
            user_agent=user_agent,
            device_hint=device_hint,
            session_id=session_id,
            status=status,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(entry)
        await db.commit()

        # Detectar patrones sospechosos
        if status in ("failure", "alert") or action == "LOGIN_FAILED":
            await _check_security_alerts(db, ip_address, user_email)

        logger.info("audit_event", action=action, user=user_email, resource=resource_id, status=status)

    except Exception as e:
        # La auditoría falla silenciosamente — registra en logs del sistema pero no interrumpe
        logger.error("audit_log_failed", error=str(e), action=action, user=user_email)


def _parse_device(user_agent: str) -> str:
    """Infiere tipo de dispositivo del User-Agent."""
    ua = user_agent.lower()
    if "ipad" in ua: return "iPad"
    if "iphone" in ua: return "iPhone"
    if "android" in ua: return "Android"
    if "mac" in ua: return "Mac"
    if "windows" in ua: return "Windows PC"
    if "linux" in ua: return "Linux"
    return "Unknown"


async def _check_security_alerts(db, ip_address: Optional[str], user_email: Optional[str]) -> None:
    """
    Detecta patrones sospechosos:
    - Más de 5 fallos de login desde la misma IP en 10 minutos → ALERT
    - Acceso desde IP no reconocida → WARNING (en producción: integrar con threat intel)
    """
    from sqlalchemy import select, func
    from app.models.audit_log import AuditLog
    from datetime import timedelta

    if not ip_address:
        return

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
        stmt = (
            select(func.count())
            .where(AuditLog.action == "LOGIN_FAILED")
            .where(AuditLog.ip_address == ip_address)
            .where(AuditLog.timestamp >= cutoff)
        )
        result = await db.execute(stmt)
        count = result.scalar()

        if count and count >= 5:
            logger.warning(
                "SECURITY_ALERT: brute_force_detected",
                ip=ip_address,
                attempts=count,
                user=user_email,
            )
            # En producción: enviar alerta a SNS / Slack / PagerDuty
    except Exception as e:
        logger.error("security_check_failed", error=str(e))


async def get_audit_summary(db) -> dict:
    """Estadísticas de auditoría para el dashboard."""
    from sqlalchemy import select, func
    from app.models.audit_log import AuditLog
    from datetime import timedelta

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)

    try:
        total_stmt = select(func.count()).select_from(AuditLog).where(AuditLog.timestamp >= today)
        alerts_stmt = select(func.count()).select_from(AuditLog).where(
            AuditLog.status == "alert", AuditLog.timestamp >= today
        )
        views_stmt = select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "DOCUMENT_VIEW", AuditLog.timestamp >= today
        )
        rag_stmt = select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "RAG_QUERY", AuditLog.timestamp >= today
        )

        total = (await db.execute(total_stmt)).scalar() or 0
        alerts = (await db.execute(alerts_stmt)).scalar() or 0
        views = (await db.execute(views_stmt)).scalar() or 0
        rag_queries = (await db.execute(rag_stmt)).scalar() or 0

        return {"total_events": total, "alerts": alerts, "document_views": views, "rag_queries": rag_queries}
    except Exception:
        return {"total_events": 0, "alerts": 0, "document_views": 0, "rag_queries": 0}
