import { api } from "@/request";
import type {
    ExecuteMockRequest,
    ExecuteMockResponse,
    GetMockDefaultsResponse,
} from "./types";

const prefix = "/v1/mock";

export const ExecuteMock = async (data: ExecuteMockRequest) => {
    return api.post<ExecuteMockResponse>(`${prefix}/executeMock`, data);
};

export const GetMockDefaults = async (api_id: number, is_latest = true) => {
    return api.get<GetMockDefaultsResponse>(`${prefix}/getMockDefaults`, {
        api_id,
        is_latest,
    });
};

export const buildMockProxyUrl = (params: {
    serviceUuid: string;
    mockPath: string;
    version?: string;
    serviceIterationId?: number;
}) => {
    const base = import.meta.env.VITE_API_BASE_URL || "";
    const query: string[] = [
        `service_uuid=${params.serviceUuid}`,
        `mock_path=${params.mockPath}`,
    ];
    if (params.serviceIterationId) {
        query.push(`service_iteration_id=${params.serviceIterationId}`);
    } else if (params.version) {
        query.push(`version=${params.version}`);
    }
    return `${base}${prefix}/proxy?${query.join("&")}`;
};
