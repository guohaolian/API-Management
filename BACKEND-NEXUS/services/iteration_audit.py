"""迭代变更审计：在关键操作点追加结构化日志。"""

import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from database.enums import IterationAuditAction
from database.models import IterationAuditLog


def append_iteration_audit(
    db: Session,
    service_iteration_id: int,
    user_id: int,
    action: IterationAuditAction,
    summary: Optional[Dict[str, Any]] = None,
) -> None:
    log = IterationAuditLog(
        service_iteration_id=service_iteration_id,
        user_id=user_id,
        action=action,
        summary=json.dumps(summary, ensure_ascii=False) if summary else None,
    )
    db.add(log)
