"""只读 API 文档门户业务逻辑。

公开访问：服务开启 docs_public 后，无需登录即可查看已发布版本。
私有预览：Owner / Maintainer / L0 登录后可预览（即使未开启公开）。
"""

from urllib.parse import unquote

from sqlalchemy.orm import Session

from database.models import Service, ServiceIteration, User, Api, ApiDraft
from services.utils import isServiceOwnerOrMaintainer, openapiTemplate, organizeReqParams, organizeRespParams


def _resolve_service(
    db: Session, service_uuid: str, version: str
) -> tuple[Service | None, Service | ServiceIteration | None, bool, dict | None]:
    service_uuid = unquote(service_uuid).strip()
    curr_service = (
        db.query(Service)
        .filter(
            Service.service_uuid == service_uuid,
            ~Service.is_deleted,
        )
        .first()
    )
    if not curr_service:
        return None, None, False, {"status": -1, "message": "Service not found"}

    if curr_service.version == version or version == "latest":  # type: ignore
        return curr_service, curr_service, True, None

    iteration = (
        db.query(ServiceIteration)
        .filter(
            ServiceIteration.service_id == curr_service.id,
            ServiceIteration.version == version,
            ServiceIteration.is_committed.is_(True),
        )
        .first()
    )
    if not iteration:
        return curr_service, None, False, {"status": -2, "message": "Service version not found"}
    return curr_service, iteration, False, None


def _can_access_docs(db: Session, curr_service: Service, user_id: int | None) -> bool:
    if curr_service.docs_public:  # type: ignore
        return True
    if user_id is None:
        return False
    user = db.get(User, user_id)
    if not user:
        return False
    return isServiceOwnerOrMaintainer(curr_service, user_id, user)


def _can_access_version(
    db: Session,
    curr_service: Service,
    service: Service | ServiceIteration,
    is_latest: bool,
    user_id: int | None,
) -> bool:
    if not _can_access_docs(db, curr_service, user_id):
        return False
    if curr_service.docs_public and not is_latest:
        return True
    if user_id is None:
        return is_latest
    user = db.get(User, user_id)
    if not user:
        return False
    if isServiceOwnerOrMaintainer(curr_service, user_id, user):
        return True
    if is_latest:
        return False
    if isinstance(service, ServiceIteration):
        return service.creator_id == user_id  # type: ignore
    return False


def docsGetServiceByUuidAndVersion(
    db: Session, service_uuid: str, version: str, user_id: int | None = None
) -> dict:
    curr_service, service, is_latest, error = _resolve_service(db, service_uuid, version)
    if error:
        return error
    assert curr_service is not None and service is not None

    if not _can_access_version(db, curr_service, service, is_latest, user_id):
        return {"status": -3, "message": "Documentation portal is not public for this service"}

    payload = service.toJson(include_relations=True)
    payload["docs_public"] = curr_service.docs_public
    return {
        "status": 200,
        "message": "Get service success",
        "service": payload,
        "is_latest": is_latest,
    }


def docsGetAllVersionsByUuid(
    db: Session, service_uuid: str, user_id: int | None = None
) -> dict:
    service_uuid = unquote(service_uuid).strip()
    curr_service = (
        db.query(Service)
        .filter(
            Service.service_uuid == service_uuid,
            ~Service.is_deleted,
        )
        .first()
    )
    if not curr_service:
        return {"status": -1, "message": "Service not found"}
    if not _can_access_docs(db, curr_service, user_id):
        return {"status": -2, "message": "Documentation portal is not public for this service"}

    service_iterations = (
        db.query(ServiceIteration)
        .filter(
            ServiceIteration.service_id == curr_service.id,
            ServiceIteration.is_committed.is_(True),
            ServiceIteration.version.isnot(None),
        )
        .order_by(ServiceIteration.id.desc())
        .all()
    )

    versions = [{"version": curr_service.version, "is_latest": True}]
    for iteration in service_iterations:
        if iteration.version != versions[0]["version"]:
            versions.append({"version": iteration.version, "is_latest": False})

    return {
        "status": 200,
        "message": "Get versions success",
        "versions": versions,
        "docs_public": curr_service.docs_public,
    }


def docsGetApiById(
    db: Session, api_id: int, is_latest: bool, user_id: int | None = None
) -> dict:
    api = db.get(Api, api_id) if is_latest else db.get(ApiDraft, api_id)
    if not api:
        return {"status": -1, "message": "Api not found"}

    if is_latest:
        curr_service = api.service
    else:
        curr_service = api.service_iteration.service

    if not _can_access_version(
        db,
        curr_service,
        api.service if is_latest else api.service_iteration,
        is_latest,
        user_id,
    ):
        return {"status": -2, "message": "Documentation portal is not public for this service"}

    request_params_by_location = organizeReqParams(api.request_params)
    response_params_by_status_code = organizeRespParams(api.response_params)
    api_info = api.toJson(
        include_relations=True,
        exclude=[
            "request_params",
            "response_params",
            "service",
            "service_iteration",
            "category",
        ],
    )
    api_info["request_params_by_location"] = request_params_by_location
    api_info["response_params_by_status_code"] = response_params_by_status_code
    return {"status": 200, "message": "Get api success", "api": api_info}


def docsExportOpenapiByUuidAndVersion(
    db: Session, service_uuid: str, version: str, user_id: int | None = None
) -> dict:
    curr_service, service, is_latest, error = _resolve_service(db, service_uuid, version)
    if error:
        return error
    assert curr_service is not None and service is not None

    if not _can_access_version(db, curr_service, service, is_latest, user_id):
        return {"status": -3, "message": "Documentation portal is not public for this service"}

    openapi = openapiTemplate(service=service, is_latest=is_latest)
    return {
        "status": 200,
        "message": "Get service success",
        "openapi_object": openapi,
        "is_latest": is_latest,
    }


def serviceUpdateDocsPublicSetting(
    db: Session, service_id: int, docs_public: bool, user_id: int
) -> dict:
    service = db.get(Service, service_id)
    if not service or service.is_deleted:
        return {"status": -1, "message": "Service not found"}
    if service.owner_id != user_id:
        user = db.get(User, user_id)
        if not user or user.level.value != 0:  # type: ignore
            return {"status": -2, "message": "Only the service owner can change docs portal setting"}

    service.docs_public = docs_public
    db.commit()
    return {
        "status": 200,
        "message": "Update docs portal setting success",
        "docs_public": docs_public,
    }
