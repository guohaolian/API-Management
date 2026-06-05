import type {
    ApiDetail,
    ApiDraftDetail,
    ParamLocation,
    ParamType,
    RequestParam,
    RequestParamDraft,
} from "@/services/api/types";
import type { MockRequestInput } from "@/services/mock/types";

type ParamNode = RequestParam | RequestParamDraft;

function coerceScalar(type: ParamType, raw: string): unknown {
    if (raw === "null" || raw === "undefined" || raw === "") return null;
    try {
        switch (type) {
            case "int":
                return parseInt(raw, 10);
            case "double":
                return parseFloat(raw);
            case "boolean": {
                const lowered = raw.trim().toLowerCase();
                if (["true", "1", "yes"].includes(lowered)) return true;
                if (["false", "0", "no"].includes(lowered)) return false;
                return Boolean(raw);
            }
            default:
                return raw;
        }
    } catch {
        return raw;
    }
}

function parseJsonValue(raw: string): unknown {
    try {
        return JSON.parse(raw);
    } catch {
        return raw;
    }
}

function typeFallback(
    type: ParamType,
    name: string,
    children?: ParamNode[],
    arrayChildType?: ParamType | null,
): unknown {
    if (type === "object") {
        return children?.length ? buildObjectFromParams(children) : {};
    }
    if (type === "array") {
        const childType = arrayChildType || "string";
        if (childType === "object" && children?.length) {
            return [buildObjectFromParams(children)];
        }
        return [typeFallback(childType, name, children, null)];
    }
    const fallbacks: Record<string, unknown> = {
        string: name ? `mock_${name}` : "mock_string",
        int: 0,
        double: 0,
        boolean: false,
        binary: "mock_binary",
    };
    return fallbacks[type] ?? "mock_value";
}

function generateValueFromParam(param: ParamNode): unknown {
    const { type, name, example, default_value, children_params, array_child_type } =
        param;

    if (example != null && example !== "") {
        if (type === "object" || type === "array") {
            const parsed = parseJsonValue(String(example));
            if (typeof parsed === "object" && parsed !== null) return parsed;
        }
        return coerceScalar(type, String(example));
    }

    if (default_value != null && default_value !== "") {
        if (type === "object" || type === "array") {
            const parsed = parseJsonValue(String(default_value));
            if (typeof parsed === "object" && parsed !== null) return parsed;
        }
        return coerceScalar(type, String(default_value));
    }

    return typeFallback(type, name, children_params, array_child_type);
}

function buildObjectFromParams(params: ParamNode[]): Record<string, unknown> {
    const result: Record<string, unknown> = {};
    for (const param of params) {
        if (!param.name) continue;
        result[param.name] = generateValueFromParam(param);
    }
    return result;
}

export function buildMockDefaultsFromApiDetail(
    apiDetail: ApiDetail | ApiDraftDetail,
): { defaultRequest: MockRequestInput; statusCodes: number[] } {
    const locations = (apiDetail.request_params_by_location ??
        {}) as Partial<Record<ParamLocation, ParamNode[]>>;
    const defaultRequest: MockRequestInput = {};

    for (const location of Object.keys(locations) as ParamLocation[]) {
        const params = locations[location];
        if (!params?.length) continue;
        if (location === "body") {
            if (
                params.length === 1 &&
                params[0].type === "object" &&
                params[0].children_params?.length
            ) {
                defaultRequest.body = buildObjectFromParams(
                    params[0].children_params,
                );
            } else {
                defaultRequest.body = buildObjectFromParams(params);
            }
        } else {
            defaultRequest[location as keyof MockRequestInput] =
                buildObjectFromParams(params);
        }
    }

    const byStatus = (apiDetail.response_params_by_status_code ??
        {}) as Record<number, unknown[]>;
    const statusCodes = Object.keys(byStatus)
        .map(Number)
        .filter((code) => (byStatus[code]?.length ?? 0) > 0)
        .sort((a, b) => a - b);

    return {
        defaultRequest,
        statusCodes: statusCodes.length ? statusCodes : [200],
    };
}
