import type { BaseResponse } from "@/services/api/types";

export interface MockRequestInput {
    query?: Record<string, unknown>;
    path?: Record<string, unknown>;
    header?: Record<string, unknown>;
    cookie?: Record<string, unknown>;
    body?: unknown;
}

export interface MockResult {
    api_id: number;
    method: string;
    path: string;
    status_code: number;
    headers: Record<string, string>;
    body: unknown;
    request_echo?: MockRequestInput;
    default_request?: MockRequestInput;
    api_name?: string;
    matched_path?: string;
}

export interface ExecuteMockRequest {
    api_id: number;
    is_latest?: boolean;
    status_code?: number;
    request?: MockRequestInput;
}

export interface ExecuteMockResponse extends BaseResponse {
    mock_result?: MockResult;
}

export interface GetMockDefaultsResponse extends BaseResponse {
    default_request?: MockRequestInput;
    status_codes?: number[];
}
