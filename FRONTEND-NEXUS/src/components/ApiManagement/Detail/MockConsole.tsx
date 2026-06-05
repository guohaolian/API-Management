import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
    Button,
    IconCommon,
    Input,
    Message,
    Select,
    Space,
    Tabs,
    Typography,
} from "@cloud-materials/common";

import styles from "../index.module.less";
import type { ApiDetail, ApiDraftDetail } from "@/services/api/types";
import type { MockRequestInput } from "@/services/mock/types";
import { ExecuteMock, buildMockProxyUrl } from "@/services/mock";
import { buildMockDefaultsFromApiDetail } from "./mockDefaults";
import { copyToClipboard, genApiMethodTag } from "@/utils";
import { toastFromError } from "@/i18n/apiMessage";

const { Text } = Typography;
const { TextArea } = Input;

interface MockConsoleProps {
    apiDetail: ApiDetail | ApiDraftDetail;
    isLatest: boolean;
    serviceUuid?: string;
    currentVersion?: string;
    serviceIterationId?: number;
}

const REQUEST_TABS = ["query", "path", "header", "cookie", "body"] as const;

const MockConsole: React.FC<MockConsoleProps> = ({
    apiDetail,
    isLatest,
    serviceUuid,
    currentVersion,
    serviceIterationId,
}) => {
    const { t } = useTranslation();
    const [searchParams] = useSearchParams();
    const [executing, setExecuting] = useState(false);
    const [statusCodes, setStatusCodes] = useState<number[]>([200]);
    const [selectedStatus, setSelectedStatus] = useState<number>(200);
    const [requestInput, setRequestInput] = useState<MockRequestInput>({});
    const [activeTab, setActiveTab] = useState<string>("body");
    const [responseJson, setResponseJson] = useState<string>("");
    const [responseStatus, setResponseStatus] = useState<number | null>(null);
    const [elapsedMs, setElapsedMs] = useState<number | null>(null);

    const applyDefaults = useCallback(() => {
        if (!apiDetail?.id) return;
        const { defaultRequest, statusCodes: codes } =
            buildMockDefaultsFromApiDetail(apiDetail);
        setRequestInput(defaultRequest);
        setStatusCodes(codes);
        setSelectedStatus(codes.includes(200) ? 200 : codes[0]);
    }, [apiDetail]);

    useEffect(() => {
        applyDefaults();
        setResponseJson("");
        setResponseStatus(null);
        setElapsedMs(null);
    }, [applyDefaults]);

    const availableTabs = useMemo(() => {
        const locations = (apiDetail.request_params_by_location ||
            {}) as Record<string, unknown[] | undefined>;
        return REQUEST_TABS.filter(
            (key) => (locations[key]?.length ?? 0) > 0 || key === "body",
        );
    }, [apiDetail.request_params_by_location]);

    useEffect(() => {
        if (!availableTabs.includes(activeTab as (typeof REQUEST_TABS)[number])) {
            setActiveTab(availableTabs[0] || "body");
        }
    }, [availableTabs, activeTab]);

    const tabEditorValue = useMemo(() => {
        const key = activeTab as keyof MockRequestInput;
        const value = requestInput[key];
        if (value === undefined || value === null) return "";
        if (typeof value === "string") return value;
        return JSON.stringify(value, null, 2);
    }, [activeTab, requestInput]);

    const handleTabValueChange = (raw: string) => {
        const key = activeTab as keyof MockRequestInput;
        if (key === "body") {
            if (!raw.trim()) {
                setRequestInput((prev) => ({ ...prev, body: undefined }));
                return;
            }
            try {
                setRequestInput((prev) => ({
                    ...prev,
                    body: JSON.parse(raw),
                }));
            } catch {
                setRequestInput((prev) => ({ ...prev, body: raw }));
            }
            return;
        }
        if (!raw.trim()) {
            setRequestInput((prev) => ({ ...prev, [key]: undefined }));
            return;
        }
        try {
            setRequestInput((prev) => ({
                ...prev,
                [key]: JSON.parse(raw),
            }));
        } catch {
            setRequestInput((prev) => ({ ...prev, [key]: raw }));
        }
    };

    const handleExecute = async () => {
        if (!apiDetail?.id) return;
        setExecuting(true);
        const started = performance.now();
        try {
            const res = await ExecuteMock({
                api_id: apiDetail.id,
                is_latest: isLatest,
                status_code: selectedStatus,
                request: requestInput,
            });
            if (res.status !== 200 || !res.mock_result) {
                throw new Error(res.message || "Mock execution failed");
            }
            setResponseStatus(res.mock_result.status_code);
            setResponseJson(
                JSON.stringify(res.mock_result.body, null, 2),
            );
            setElapsedMs(Math.round(performance.now() - started));
            Message.success(t("mockConsole.executeSuccess"));
        } catch (error) {
            Message.error(toastFromError(error, "mockConsole.executeFailed"));
        } finally {
            setExecuting(false);
        }
    };

    const resolvedServiceUuid = useMemo(() => {
        if (serviceUuid) return serviceUuid;
        const fromQuery = searchParams.get("uuid");
        if (fromQuery) return fromQuery;
        const service = (apiDetail as ApiDetail).service;
        return service?.service_uuid || "";
    }, [serviceUuid, searchParams, apiDetail]);

    const proxyUrl = useMemo(() => {
        if (!resolvedServiceUuid || !apiDetail?.path) return "";
        return buildMockProxyUrl({
            serviceUuid: resolvedServiceUuid,
            mockPath: apiDetail.path,
            version: serviceIterationId
                ? undefined
                : currentVersion || "latest",
            serviceIterationId,
        });
    }, [
        resolvedServiceUuid,
        apiDetail?.path,
        currentVersion,
        serviceIterationId,
    ]);

    const tabTitle = (key: string) => {
        const map: Record<string, string> = {
            query: t("apiDetail.queryParams"),
            path: t("apiDetail.pathParams"),
            header: t("apiDetail.headerParams"),
            cookie: t("apiDetail.cookieParams"),
            body: t("apiDetail.bodyParams"),
        };
        return map[key] || key;
    };

    return (
        <Space direction="vertical" size={12} className={styles.mockConsole}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>
                <IconCommon /> {t("mockConsole.title")}
            </div>
            <Text type="secondary">{t("mockConsole.description")}</Text>

            {proxyUrl && (
                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                    <Text>{t("mockConsole.proxyUrl")}</Text>
                    <Space style={{ width: "100%" }}>
                        <Space size={6} style={{ flex: 1, wordBreak: "break-all" }}>
                            {genApiMethodTag(apiDetail.method, "small")}
                            <Text>{proxyUrl}</Text>
                        </Space>
                        <Button
                            size="mini"
                            onClick={() =>
                                copyToClipboard(proxyUrl).then(() =>
                                    Message.success(t("mockConsole.copied")),
                                )
                            }
                        >
                            {t("mockConsole.copyUrl")}
                        </Button>
                    </Space>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                        {t("mockConsole.proxyHint")}
                    </Text>
                </Space>
            )}

            <div>
                <Space
                    align="center"
                    style={{ width: "100%", justifyContent: "space-between" }}
                >
                    <Space>
                        <Text>{t("mockConsole.responseStatus")}</Text>
                        <Select
                            size="small"
                            style={{ width: 120 }}
                            value={selectedStatus}
                            onChange={setSelectedStatus}
                            options={statusCodes.map((code) => ({
                                label: String(code),
                                value: code,
                            }))}
                        />
                    </Space>
                    <Space>
                        <Button size="small" onClick={applyDefaults}>
                            {t("mockConsole.resetRequest")}
                        </Button>
                        <Button
                            type="primary"
                            size="small"
                            loading={executing}
                            onClick={handleExecute}
                        >
                            {t("mockConsole.sendMock")}
                        </Button>
                    </Space>
                </Space>

                <Tabs
                    activeTab={activeTab}
                    onChange={setActiveTab}
                    style={{ marginTop: 12 }}
                >
                    {availableTabs.map((key) => (
                        <Tabs.TabPane key={key} title={tabTitle(key)}>
                            <TextArea
                                value={tabEditorValue}
                                onChange={handleTabValueChange}
                                autoSize={{ minRows: 4, maxRows: 16 }}
                                placeholder={t("mockConsole.requestPlaceholder")}
                            />
                        </Tabs.TabPane>
                    ))}
                </Tabs>

                <div style={{ marginTop: 16 }}>
                    <Space style={{ marginBottom: 8 }}>
                        <Text style={{ fontWeight: 500 }}>
                            {t("mockConsole.response")}
                        </Text>
                        {responseStatus !== null && (
                            <Text type="secondary">
                                HTTP {responseStatus}
                                {elapsedMs !== null &&
                                    ` · ${elapsedMs}ms`}
                            </Text>
                        )}
                    </Space>
                    <TextArea
                        value={responseJson}
                        readOnly
                        autoSize={{ minRows: 6, maxRows: 20 }}
                        placeholder={t("mockConsole.responsePlaceholder")}
                        className={styles.mockResponseArea}
                    />
                </div>
            </div>
        </Space>
    );
};

export default MockConsole;
