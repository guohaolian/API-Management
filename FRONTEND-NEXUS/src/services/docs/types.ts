import type { BaseResponse, ServiceDetail, ServiceIterationDetail } from "../service/types";
import type { ApiDetail } from "../api/types";

export interface DocsGetServiceByUuidAndVersionResponse extends BaseResponse {
    service: ServiceDetail | ServiceIterationDetail;
    is_latest: boolean;
}

export interface DocsGetAllVersionsByUuidResponse extends BaseResponse {
    versions: { version: string; is_latest: boolean }[];
    docs_public?: boolean;
}

export interface DocsGetApiByIdResponse extends BaseResponse {
    api: ApiDetail;
}

export interface DocsExportOpenapiResponse extends BaseResponse {
    openapi_object: Record<string, unknown>;
    is_latest: boolean;
}
