"""将迭代草稿提交为正式 Service 版本（不含权限与审批门控）。"""

from sqlalchemy.orm import Session

from database.models import (
    Api,
    ApiDraft,
    RequestParam,
    RequestParamDraft,
    ResponseParam,
    ResponseParamDraft,
    ServiceIteration,
)
from database.enums import IterationApprovalStatus


def commit_iteration_core(
    db: Session,
    service_iteration: ServiceIteration,
    new_version: str,
) -> dict:
    """把草稿同步到正式表并标记迭代已提交。调用方负责权限校验与 commit。"""
    service = service_iteration.service
    if new_version == service.version:
        return {"status": -1, "message": "New version is the same as current version"}

    service.description = service_iteration.description
    service.version = new_version

    db.query(Api).filter(Api.service_id == service.id).delete(synchronize_session=False)

    for api_draft in service_iteration.api_drafts:
        new_api = Api(
            service_id=service.id,
            owner_id=api_draft.owner_id,
            category_id=api_draft.category_id,
            name=api_draft.name,
            method=api_draft.method,
            path=api_draft.path,
            description=api_draft.description,
            level=api_draft.level,
            is_enabled=api_draft.is_enabled,
        )
        db.add(new_api)
        db.flush()

        req_param_id_mapping = {}
        for req in api_draft.request_params:
            request_param = RequestParam(
                api_id=new_api.id,
                name=req.name,
                location=req.location,
                type=req.type,
                required=req.required,
                default_value=req.default_value,
                description=req.description,
                example=req.example,
                array_child_type=req.array_child_type,
                parent_param_id=None,
            )
            db.add(request_param)
            db.flush()
            req_param_id_mapping[req.id] = request_param.id

        for req in api_draft.request_params:
            if req.parent_param_id is not None:
                param = (
                    db.query(RequestParam)
                    .filter(RequestParam.id == req_param_id_mapping[req.id])
                    .first()
                )
                if param:
                    param.parent_param_id = req_param_id_mapping[req.parent_param_id]

        resp_param_id_mapping = {}
        for resp in api_draft.response_params:
            response_param = ResponseParam(
                api_id=new_api.id,
                status_code=resp.status_code,
                name=resp.name,
                type=resp.type,
                required=resp.required,
                description=resp.description,
                example=resp.example,
                array_child_type=resp.array_child_type,
                parent_param_id=None,
            )
            db.add(response_param)
            db.flush()
            resp_param_id_mapping[resp.id] = response_param.id

        for resp in api_draft.response_params:
            if resp.parent_param_id is not None:
                param = (
                    db.query(ResponseParam)
                    .filter(ResponseParam.id == resp_param_id_mapping[resp.id])
                    .first()
                )
                if param:
                    param.parent_param_id = resp_param_id_mapping[resp.parent_param_id]

    service_iteration.version = new_version
    service_iteration.is_committed = True
    service_iteration.approval_status = IterationApprovalStatus.COMMITTED
    db.commit()

    return {
        "status": 200,
        "message": "Commit service iteration success",
        "service_id": service.id,
        "service_iteration_id": service_iteration.id,
        "version": new_version,
    }
