"""迭代审批：提交、通过、驳回、待审列表与审计查询。"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from database.enums import IterationApprovalStatus, IterationAuditAction
from database.models import IterationAuditLog, Service, ServiceIteration, User
from mailer import send_email
from services.iteration_audit import append_iteration_audit
from services.iteration_commit import commit_iteration_core
from services.utils import checkServiceIterationPermission
from services.version_diff import compare_iteration_change_preview


def _is_owner(user_id: int, service: Service) -> bool:
    return service.owner_id == user_id


def _is_l0(user: User) -> bool:
    return user.level.value == 0  # type: ignore


def _can_direct_commit(service: Service, user_id: int, user: User) -> bool:
    return not service.requires_iteration_approval or _is_owner(user_id, service) or _is_l0(user)


async def _notify_owner_submit(
    service_iteration: ServiceIteration, operator: User
) -> None:
    service = service_iteration.service
    owner = service.owner
    if not owner or not owner.email:
        return
    mail_res = await send_email(
        to_email=[owner.email],
        subject=f"[NEXUS] 迭代待审批：{service.service_uuid}",
        content=(
            f"服务 {service.service_uuid} 有新的迭代提交待您审批。\n"
            f"提议版本：{service_iteration.proposed_version}\n"
            f"提交人：{operator.nickname} ({operator.username})\n"
        ),
    )
    if mail_res["status"] != 200:
        print(
            f"Send submit notification failed: {mail_res.get('message', 'Unknown error')}"
        )


async def _notify_reject(
    service: Service, submitter: User, review_comment: str
) -> None:
    if not submitter.email:
        return
    mail_res = await send_email(
        to_email=[submitter.email],
        subject=f"[NEXUS] 迭代已驳回：{service.service_uuid}",
        content=(
            f"您对服务 {service.service_uuid} 的迭代提交已被驳回。\n"
            f"意见：{review_comment}\n"
            f"您可在同一迭代中修改后重新提交。\n"
        ),
    )
    if mail_res["status"] != 200:
        print(
            f"Send reject notification failed: {mail_res.get('message', 'Unknown error')}"
        )


async def _notify_commit(
    service: Service, new_version: str, operator: User, event: str, comment: str = ""
) -> None:
    recipients = {service.owner.email}
    for maintainer in service.maintainers:
        if maintainer.email:
            recipients.add(maintainer.email)
    extra = f"\n审批意见：{comment}" if comment else ""
    await send_email(
        to_email=list(recipients),
        subject=f"服务 {service.service_uuid} 版本更新",
        content=(
            f"您好！服务 {service.service_uuid} 已{event}版本 {new_version}。\n"
            f"操作人：{operator.nickname} ({operator.username}){extra}\n"
        ),
    )


async def serviceSubmitIterationForApproval(
    db: Session, service_iteration_id: int, new_version: str, user_id: int
) -> dict:
    check_res = checkServiceIterationPermission(
        db=db, service_iteration_id=service_iteration_id, user_id=user_id
    )
    if not check_res["is_ok"]:
        return check_res.get("error", check_res)

    service_iteration = check_res["service_iteration"]
    service = service_iteration.service
    if not service.requires_iteration_approval:
        return {"status": -40, "message": "This service does not require iteration approval"}

    status = service_iteration.approval_status
    if status not in (
        IterationApprovalStatus.DRAFT,
        IterationApprovalStatus.REJECTED,
    ):
        return {"status": -41, "message": "Iteration is not in a submittable state"}

    if new_version == service.version:
        return {"status": -1, "message": "New version is the same as current version"}

    user = check_res["user"]
    now = datetime.now(timezone.utc)
    service_iteration.proposed_version = new_version
    service_iteration.approval_status = IterationApprovalStatus.PENDING
    service_iteration.submitted_at = now
    service_iteration.submitted_by_id = user_id
    service_iteration.reviewed_at = None
    service_iteration.reviewed_by_id = None
    service_iteration.review_comment = None
    append_iteration_audit(
        db,
        service_iteration_id,
        user_id,
        IterationAuditAction.SUBMITTED_FOR_APPROVAL,
        {"proposed_version": new_version},
    )
    db.commit()
    try:
        await _notify_owner_submit(service_iteration, user)
    except Exception as e:
        print(f"Send submit notification failed: {e}")
    return {
        "status": 200,
        "message": "Submit iteration for approval success",
        "service_iteration_id": service_iteration.id,
        "approval_status": IterationApprovalStatus.PENDING.value,
    }


async def serviceApproveIteration(
    db: Session, service_iteration_id: int, user_id: int, review_comment: str = ""
) -> dict:
    service_iteration = db.get(ServiceIteration, service_iteration_id)
    if not service_iteration or service_iteration.is_committed:
        return {"status": -10, "message": "Service iteration not found or committed"}

    service = service_iteration.service
    user = db.get(User, user_id)
    if not user:
        return {"status": -6, "message": "User not found"}
    if not _is_owner(user_id, service) and not _is_l0(user):
        return {"status": -50, "message": "Only the service owner can approve iterations"}

    if service_iteration.approval_status != IterationApprovalStatus.PENDING:
        return {"status": -51, "message": "Iteration is not pending approval"}

    new_version = service_iteration.proposed_version
    if not new_version:
        return {"status": -52, "message": "Proposed version is missing"}

    now = datetime.now(timezone.utc)
    service_iteration.reviewed_at = now
    service_iteration.reviewed_by_id = user_id
    service_iteration.review_comment = review_comment or None
    append_iteration_audit(
        db,
        service_iteration_id,
        user_id,
        IterationAuditAction.APPROVED,
        {"proposed_version": new_version, "review_comment": review_comment},
    )
    db.flush()

    res = commit_iteration_core(db, service_iteration, new_version)
    if res["status"] != 200:
        db.rollback()
        return res

    try:
        await _notify_commit(service, new_version, user, "审批通过并发布至", review_comment)
    except Exception as e:
        print(f"Send approve notification failed: {e}")

    return res


async def serviceRejectIteration(
    db: Session,
    service_iteration_id: int,
    user_id: int,
    review_comment: str,
) -> dict:
    if not review_comment or not review_comment.strip():
        return {"status": -53, "message": "Review comment is required when rejecting"}

    service_iteration = db.get(ServiceIteration, service_iteration_id)
    if not service_iteration or service_iteration.is_committed:
        return {"status": -10, "message": "Service iteration not found or committed"}

    service = service_iteration.service
    user = db.get(User, user_id)
    if not user:
        return {"status": -6, "message": "User not found"}
    if not _is_owner(user_id, service) and not _is_l0(user):
        return {"status": -50, "message": "Only the service owner can reject iterations"}

    if service_iteration.approval_status != IterationApprovalStatus.PENDING:
        return {"status": -51, "message": "Iteration is not pending approval"}

    now = datetime.now(timezone.utc)
    service_iteration.approval_status = IterationApprovalStatus.REJECTED
    service_iteration.reviewed_at = now
    service_iteration.reviewed_by_id = user_id
    service_iteration.review_comment = review_comment.strip()
    append_iteration_audit(
        db,
        service_iteration_id,
        user_id,
        IterationAuditAction.REJECTED,
        {"review_comment": review_comment.strip()},
    )
    db.commit()

    submitter = service_iteration.submitted_by
    if submitter and submitter.email:
        try:
            await _notify_reject(service, submitter, review_comment)
        except Exception as e:
            print(f"Send reject notification failed: {e}")

    return {
        "status": 200,
        "message": "Reject iteration success",
        "service_iteration_id": service_iteration.id,
        "approval_status": IterationApprovalStatus.REJECTED.value,
    }


def serviceGetPendingIterations(
    db: Session, user_id: int, page_size: int = 20, current_page: int = 1
) -> dict:
    user = db.get(User, user_id)
    if not user:
        return {"status": -6, "message": "User not found"}

    q = db.query(ServiceIteration).filter(
        ServiceIteration.approval_status == IterationApprovalStatus.PENDING,
        ~ServiceIteration.is_committed,
    )
    if not _is_l0(user):
        q = q.join(Service).filter(Service.owner_id == user_id)

    total = q.count()
    rows = (
        q.order_by(ServiceIteration.submitted_at.desc())
        .limit(page_size)
        .offset((current_page - 1) * page_size)
        .all()
    )
    items = []
    for it in rows:
        svc = it.service
        items.append(
            {
                "service_iteration_id": it.id,
                "service_id": svc.id,
                "service_uuid": svc.service_uuid,
                "base_version": it.base_version or svc.version,
                "proposed_version": it.proposed_version,
                "submitted_at": it.submitted_at.isoformat() if it.submitted_at else None,
                "submitted_by": it.submitted_by.toJson(include=["id", "username", "nickname", "email"])
                if it.submitted_by
                else None,
                "creator": it.creator.toJson(include=["id", "username", "nickname", "email"])
                if it.creator
                else None,
            }
        )
    return {
        "status": 200,
        "message": "Get pending iterations success",
        "iterations": items,
        "total": total,
    }


def _can_view_iteration_audit(
    db: Session, service_iteration: ServiceIteration, user_id: int
) -> tuple[bool, Optional[dict]]:
    user = db.get(User, user_id)
    if not user:
        return False, {"status": -6, "message": "User not found"}
    service = service_iteration.service
    if _is_l0(user):
        return True, None
    if service.owner_id == user_id:
        return True, None
    if service_iteration.creator_id == user_id:
        return True, None
    if user in service.maintainers:
        return True, None
    return False, {"status": -30, "message": "No permission to view iteration audit"}


def serviceGetIterationAuditLog(
    db: Session,
    service_iteration_id: int,
    user_id: int,
    page_size: int = 50,
    current_page: int = 1,
) -> dict:
    service_iteration = db.get(ServiceIteration, service_iteration_id)
    if not service_iteration:
        return {"status": -10, "message": "Service iteration not found"}

    ok, err = _can_view_iteration_audit(db, service_iteration, user_id)
    if not ok:
        return err  # type: ignore

    q = db.query(IterationAuditLog).filter(
        IterationAuditLog.service_iteration_id == service_iteration_id
    )
    total = q.count()
    logs = (
        q.order_by(IterationAuditLog.created_at.desc())
        .limit(page_size)
        .offset((current_page - 1) * page_size)
        .all()
    )
    import json

    items = []
    for log in logs:
        summary = None
        if log.summary:
            try:
                summary = json.loads(log.summary)
            except json.JSONDecodeError:
                summary = log.summary
        items.append(
            {
                "id": log.id,
                "action": log.action.value,
                "summary": summary,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "user": log.user.toJson(include=["id", "username", "nickname", "email"])
                if log.user
                else None,
            }
        )
    return {
        "status": 200,
        "message": "Get iteration audit log success",
        "logs": items,
        "total": total,
    }


def serviceGetIterationChangePreview(
    db: Session, service_iteration_id: int, user_id: int
) -> dict:
    service_iteration = db.get(ServiceIteration, service_iteration_id)
    if not service_iteration:
        return {"status": -10, "message": "Service iteration not found"}

    ok, err = _can_view_iteration_audit(db, service_iteration, user_id)
    if not ok:
        return err  # type: ignore

    return compare_iteration_change_preview(db, service_iteration)


def serviceUpdateServiceApprovalSetting(
    db: Session, service_id: int, requires_iteration_approval: bool, user_id: int
) -> dict:
    service = db.get(Service, service_id)
    if not service:
        return {"status": -1, "message": "Service not found"}
    user = db.get(User, user_id)
    if not user:
        return {"status": -6, "message": "User not found"}
    if service.owner_id != user_id and not _is_l0(user):
        return {"status": -2, "message": "You are not the owner of this service"}

    service.requires_iteration_approval = requires_iteration_approval
    db.commit()
    return {
        "status": 200,
        "message": "Update service approval setting success",
        "requires_iteration_approval": requires_iteration_approval,
    }


def check_direct_commit_allowed(service: Service, user_id: int, user: User) -> Optional[dict]:
    """若不允许直接发布，返回 error dict。"""
    if _can_direct_commit(service, user_id, user):
        return None
    return {
        "status": -42,
        "message": "This service requires owner approval. Please submit for approval instead",
    }
