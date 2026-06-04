import type { HttpMethod } from "../api/types";
import type { UserProfile } from "../user/types";

export interface BaseResponse {
    status: number;
    message: string;
}

export type IterationApprovalStatus =
    | "draft"
    | "pending"
    | "rejected"
    | "committed";

export interface ServiceItem {
    id: number;
    service_uuid: string;
    version: string;
    description?: string | null;
    owner_id: number;
    created_at: string;
    is_deleted: boolean;
    requires_iteration_approval?: boolean;
    owner?: UserProfile | null;
}

export interface DeletedServiceItem extends ServiceItem {
    deleted_at: string;
}

export interface AllServiceItem extends DeletedServiceItem {}

export interface ApiBrief {
    id: number;
    name: string;
    method: HttpMethod;
    path: string;
    description?: string | null;
    level?: string;
    is_enabled?: boolean;
    category_id?: number | null;
}

export interface ApiCategory {
    id: number;
    name: string;
    description?: string | null;
}

export interface ServiceIteration {
    id: number;
    service_id: number;
    creator_id?: number | null;
    version?: string | null;
    description?: string | null;
    is_committed: boolean;
    created_at?: string;
    base_version?: string | null;
    approval_status?: IterationApprovalStatus;
    proposed_version?: string | null;
    submitted_at?: string | null;
    review_comment?: string | null;
    submitted_by?: UserProfile | null;
    reviewed_by?: UserProfile | null;
}

export interface ServiceDetail extends ServiceItem {
    owner_id: number;
    owner?: UserProfile | null;
    maintainers?: UserProfile[];
    apis?: ApiBrief[];
    api_categories?: ApiCategory[];
    iterations?: ServiceIteration[];
    created_at: string;
    updated_at?: string;
    is_deleted: boolean;
    deleted_at?: string;
}

export interface ServiceIterationDetail extends ServiceIteration {
    service?: ServiceItem;
    creator: UserProfile;
    api_drafts?: ApiBrief[];
}

export interface ServiceListResponse extends BaseResponse {
    services: ServiceItem[];
    total: number;
}

export interface GetServiceByIdResponse extends BaseResponse {
    service: ServiceDetail;
}

export interface GetServiceByUuidAndVersionResponse extends BaseResponse {
    service: ServiceDetail | ServiceIterationDetail;
    is_latest: boolean;
}

export interface GetAllVersionsByUuidResponse extends BaseResponse {
    versions: {
        version: string;
        is_latest: boolean;
    }[];
}

export interface CreateNewServiceRequest {
    service_uuid: string;
    description: string;
}

export interface CreateNewServiceResponse extends BaseResponse {
    service: ServiceDetail;
}

export interface GetAllDeletedServicesByUserIdResponse extends BaseResponse {
    deleted_services: DeletedServiceItem[];
    total: number;
}

export interface GetAllServicesResponse extends BaseResponse {
    services: AllServiceItem[];
    total: number;
}

export interface DeleteServiceByIdRequest {
    id: number;
}

export type DeleteServiceByIdResponse = BaseResponse;

export interface RestoreServiceByIdRequest {
    id: number;
}

export type RestoreServiceByIdResponse = BaseResponse;

export interface DeleteIterationByIdRequest {
    service_iteration_id: number;
}

export type DeleteIterationByIdResponse = BaseResponse;

export interface GetIterationByIdResponse extends BaseResponse {
    iteration: ServiceIterationDetail;
}

export interface StartIterationRequest {
    service_id: number;
}

export interface StartIterationResponse extends BaseResponse {
    service_iteration_id: number;
}

export interface CommitIterationRequest {
    service_iteration_id: number;
    new_version: string;
}

export interface CommitIterationResponse extends BaseResponse {
    service_id: number;
    service_iteration_id: number;
    version: string;
}

export interface UpdateDescriptionRequest {
    service_iteration_id: number;
    description: string;
}

export type UpdateDescriptionResponse = BaseResponse;

export interface IsServiceMaintainerRequest {
    service_id: number;
    candidate_id: number;
}

export interface IsServiceMaintainerResponse extends BaseResponse {
    is_current_maintainer: boolean;
}

export interface AddOrRemoveServiceMaintainerByIdRequest {
    service_id: number;
    candidate_id: number;
}

export interface AddOrRemoveServiceMaintainerByIdResponse extends BaseResponse {
    is_current_maintainer: boolean;
}

export interface ExportOpenapiByUuidAndVersionResponse extends BaseResponse {
    openapi_object: Record<string, any>;
    is_latest: boolean;
}

export type DiffChangeType = "added" | "removed" | "modified";

export interface FieldChange {
    field: string;
    old?: unknown;
    new?: unknown;
}

export interface ParamDiffEntry {
    path: string;
    param?: Record<string, unknown>;
    field_changes?: FieldChange[];
    base?: Record<string, unknown>;
    compare?: Record<string, unknown>;
}

export interface ParamsDiffBlock {
    added: ParamDiffEntry[];
    removed: ParamDiffEntry[];
    modified: ParamDiffEntry[];
    has_changes?: boolean;
}

export interface ApiDiffSnapshot {
    key: string;
    name: string;
    method: string;
    path: string;
    description?: string | null;
    level?: string;
    is_enabled?: boolean;
    category_id?: number | null;
}

export interface ModifiedApiDiff extends ApiDiffSnapshot {
    field_changes: FieldChange[];
    request_params: ParamsDiffBlock;
    response_params: ParamsDiffBlock;
}

export interface CategoryDiffItem {
    id: number;
    name: string;
    description?: string;
}

export interface ModifiedCategoryDiff {
    id: number;
    field_changes: FieldChange[];
    base: CategoryDiffItem;
    compare: CategoryDiffItem;
}

export interface CompareVersionsSummary {
    service_changed: boolean;
    categories_added: number;
    categories_removed: number;
    categories_modified: number;
    apis_added: number;
    apis_removed: number;
    apis_modified: number;
}

export interface CompareVersionsByUuidResponse extends BaseResponse {
    base_version: string;
    compare_version: string;
    service_diff: {
        field_changes: FieldChange[];
        base_description: string;
        compare_description: string;
    };
    categories_diff: {
        added: CategoryDiffItem[];
        removed: CategoryDiffItem[];
        modified: ModifiedCategoryDiff[];
    };
    apis_diff: {
        added: ApiDiffSnapshot[];
        removed: ApiDiffSnapshot[];
        modified: ModifiedApiDiff[];
    };
    summary: CompareVersionsSummary;
}

export interface ImportOpenapiToNewIterationRequest {
    service_id: number;
    openapi_object: Record<string, any>;
}

export interface ImportOpenapiToNewIterationResponse extends BaseResponse {
    service_iteration_id: number;
    imported: {
        apis: number;
        request_params: number;
        response_params: number;
        categories: number;
        warnings: string[];
    };
}

export interface ImportOpenapiToIterationRequest {
    service_iteration_id: number;
    openapi_object: Record<string, any>;
}

export type ImportOpenapiToIterationResponse = ImportOpenapiToNewIterationResponse;

export interface SubmitIterationForApprovalRequest {
    service_iteration_id: number;
    new_version: string;
}

export type SubmitIterationForApprovalResponse = BaseResponse & {
    service_iteration_id: number;
    approval_status: IterationApprovalStatus;
};

export interface ApproveIterationRequest {
    service_iteration_id: number;
    review_comment?: string;
}

export type ApproveIterationResponse = CommitIterationResponse;

export interface RejectIterationRequest {
    service_iteration_id: number;
    review_comment: string;
}

export type RejectIterationResponse = BaseResponse & {
    service_iteration_id: number;
    approval_status: IterationApprovalStatus;
};

export interface PendingIterationItem {
    service_iteration_id: number;
    service_id: number;
    service_uuid: string;
    base_version: string;
    proposed_version: string;
    submitted_at: string | null;
    submitted_by: UserProfile | null;
    creator: UserProfile | null;
}

export interface GetPendingIterationsResponse extends BaseResponse {
    iterations: PendingIterationItem[];
    total: number;
}

export interface IterationAuditLogItem {
    id: number;
    action: string;
    summary: Record<string, unknown> | string | null;
    created_at: string | null;
    user: UserProfile | null;
}

export interface GetIterationAuditLogResponse extends BaseResponse {
    logs: IterationAuditLogItem[];
    total: number;
}

export type GetIterationChangePreviewResponse = CompareVersionsByUuidResponse;

export interface UpdateServiceApprovalSettingRequest {
    service_id: number;
    requires_iteration_approval: boolean;
}

export interface UpdateServiceApprovalSettingResponse extends BaseResponse {
    requires_iteration_approval: boolean;
}

export type ServiceRange =
    | "MyServices"
    | "MyMaintainedServices"
    | "HisServices"
    | "AllServices"
    | "MyDeletedServices";

export interface Pagination {
    page_size: number;
    current_page: number;
    total: number;
}
