import { api } from "@/request";
import type {
    DocsGetServiceByUuidAndVersionResponse,
    DocsGetAllVersionsByUuidResponse,
    DocsGetApiByIdResponse,
    DocsExportOpenapiResponse,
} from "./types";

const prefix = "/v1/docs";

export const DocsGetServiceByUuidAndVersion = async (
    service_uuid: string,
    version: string,
) => {
    return api.get<DocsGetServiceByUuidAndVersionResponse>(
        `${prefix}/getServiceByUuidAndVersion`,
        { service_uuid, version },
    );
};

export const DocsGetAllVersionsByUuid = async (service_uuid: string) => {
    return api.get<DocsGetAllVersionsByUuidResponse>(
        `${prefix}/getAllVersionsByUuid`,
        { service_uuid },
    );
};

export const DocsGetApiById = async (api_id: number, is_latest: boolean) => {
    return api.get<DocsGetApiByIdResponse>(`${prefix}/getApiById`, {
        api_id,
        is_latest,
    });
};

export const DocsExportOpenapiByUuidAndVersion = async (
    service_uuid: string,
    version: string,
) => {
    return api.get<DocsExportOpenapiResponse>(
        `${prefix}/exportOpenapiByUuidAndVersion`,
        { service_uuid, version },
    );
};
