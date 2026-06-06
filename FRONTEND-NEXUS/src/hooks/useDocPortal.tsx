import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
    Message,
    Popover,
    Space,
    Typography,
} from "@cloud-materials/common";
import { useTranslation } from "react-i18next";

import {
    DocsGetAllVersionsByUuid,
    DocsGetApiById,
    DocsGetServiceByUuidAndVersion,
} from "@/services/docs";
import type { ApiDetail } from "@/services/api/types";
import type {
    ApiBrief,
    ApiCategory,
    ServiceDetail,
    ServiceIterationDetail,
} from "@/services/service/types";
import { genApiMethodTag } from "@/utils";
import { toastFromError } from "@/i18n/apiMessage";

const { Text, Ellipsis } = Typography;

export const useDocPortal = (serviceUuid: string) => {
    const { t, i18n } = useTranslation();
    const [loading, setLoading] = useState(false);
    const [accessDenied, setAccessDenied] = useState(false);
    const [versions, setVersions] = useState<
        { version: string; is_latest: boolean }[]
    >([]);
    const [currentVersion, setCurrentVersion] = useState("");
    const [isLatest, setIsLatest] = useState(true);
    const [docsPublic, setDocsPublic] = useState(false);
    const [serviceDetail, setServiceDetail] = useState<
        ServiceDetail | ServiceIterationDetail
    >({} as ServiceDetail);
    const [apiCategories, setApiCategories] = useState<ApiCategory[]>([]);
    const [apis, setApis] = useState<ApiBrief[]>([]);

    const fetchAllVersions = useCallback(async () => {
        if (!serviceUuid) return;
        setLoading(true);
        setAccessDenied(false);
        try {
            const res = await DocsGetAllVersionsByUuid(serviceUuid);
            if (res.status !== 200) {
                setAccessDenied(true);
                setVersions([]);
                throw new Error(res.message);
            }
            setDocsPublic(!!res.docs_public);
            setVersions(res.versions.filter((v) => v.version) || []);
            const latestVersion = res.versions?.[0]?.version || "";
            setCurrentVersion(latestVersion);
            setIsLatest(res.versions?.[0]?.is_latest || false);
        } catch (err: unknown) {
            Message.warning(toastFromError(err, "docPortal.loadFailed"));
        } finally {
            setLoading(false);
        }
    }, [serviceUuid]);

    useEffect(() => {
        fetchAllVersions();
    }, [fetchAllVersions]);

    const fetchServiceDetail = useCallback(
        async (version: string) => {
            if (!serviceUuid || !version) return;
            setLoading(true);
            try {
                const res = await DocsGetServiceByUuidAndVersion(
                    serviceUuid,
                    version,
                );
                if (res.status !== 200) {
                    setAccessDenied(true);
                    setServiceDetail({} as ServiceDetail);
                    throw new Error(res.message);
                }
                setAccessDenied(false);
                setServiceDetail(res.service || ({} as ServiceDetail));
                setIsLatest(res.is_latest);
                if ("docs_public" in res.service) {
                    setDocsPublic(!!res.service.docs_public);
                }
                if ("api_categories" in res.service) {
                    setApiCategories(res.service.api_categories || []);
                }
                if ("apis" in res.service || "api_drafts" in res.service) {
                    setApis(
                        ("apis" in res.service
                            ? res.service.apis
                            : "api_drafts" in res.service
                              ? res.service.api_drafts
                              : []) || [],
                    );
                }
            } catch (err: unknown) {
                Message.warning(toastFromError(err, "docPortal.loadFailed"));
            } finally {
                setLoading(false);
            }
        },
        [serviceUuid],
    );

    useEffect(() => {
        if (currentVersion) {
            fetchServiceDetail(currentVersion);
        }
    }, [currentVersion, fetchServiceDetail]);

    const treeData = useMemo(() => {
        if (!apiCategories || !apis) {
            return [] as any[];
        }
        const categoryMap = new Map<number, any>();
        apiCategories.forEach((cat) => {
            categoryMap.set(cat.id, {
                key: `category-${cat.id}`,
                searchText: cat.name.toLowerCase(),
                title: (
                    <Popover content={cat.description}>
                        <Text>{cat.name}</Text>
                    </Popover>
                ),
                children: [] as any[],
                selectable: false,
                draggable: false,
            });
        });
        const uncategorizedGroup = {
            key: "category-null",
            searchText: t("common.uncategorized"),
            title: <Text>{t("common.uncategorized")}</Text>,
            children: [] as any[],
            selectable: false,
            draggable: false,
        };

        apis.sort((a, b) => a.method.localeCompare(b.method)).forEach((api) => {
            const node = {
                key: api.id.toString(),
                searchText: `${api.method} ${api.name} ${api.path}`.toLowerCase(),
                title: (
                    <Space style={{ fontWeight: 500 }}>
                        {genApiMethodTag(api.method, "small")}
                        {api.name}
                        <Ellipsis
                            style={{ color: "#6e7687", fontSize: 10 }}
                            rows={1}
                            showTooltip
                        >
                            {api.path}
                        </Ellipsis>
                    </Space>
                ),
            };
            if (api.category_id == null) {
                uncategorizedGroup.children.push(node);
            } else {
                const group = categoryMap.get(api.category_id);
                if (group) {
                    group.children.push(node);
                } else {
                    uncategorizedGroup.children.push(node);
                }
            }
        });

        return [...Array.from(categoryMap.values()), uncategorizedGroup];
    }, [apiCategories, apis, i18n.language, t]);

    const serviceDescription = useMemo(() => {
        if ("description" in serviceDetail) {
            return serviceDetail.description || "";
        }
        return "";
    }, [serviceDetail]);

    return {
        loading,
        accessDenied,
        versions,
        currentVersion,
        setCurrentVersion,
        isLatest,
        docsPublic,
        serviceDetail,
        serviceDescription,
        treeData,
    };
};

export const useDocApiDetail = (
    apiId: number,
    isLatest: boolean,
    version: string,
) => {
    const [loading, setLoading] = useState(false);
    const [apiDetail, setApiDetail] = useState<ApiDetail>({} as ApiDetail);
    const requestSeqRef = useRef(0);

    useEffect(() => {
        setApiDetail({} as ApiDetail);
    }, [version, isLatest]);

    const fetchApiDetail = useCallback(async () => {
        const requestSeq = ++requestSeqRef.current;
        if (!apiId || apiId <= 0) {
            setApiDetail({} as ApiDetail);
            setLoading(false);
            return;
        }
        setLoading(true);
        try {
            const res = await DocsGetApiById(apiId, isLatest);
            if (requestSeq !== requestSeqRef.current) return;
            if (res.status !== 200) {
                setApiDetail({} as ApiDetail);
                throw new Error(res.message);
            }
            setApiDetail(res.api || ({} as ApiDetail));
        } catch (err: unknown) {
            if (requestSeq !== requestSeqRef.current) return;
            setApiDetail({} as ApiDetail);
            Message.warning(toastFromError(err, "toast.fetchApiDetailFailed"));
        } finally {
            if (requestSeq === requestSeqRef.current) {
                setLoading(false);
            }
        }
    }, [apiId, isLatest, version]);

    useEffect(() => {
        fetchApiDetail();
    }, [fetchApiDetail]);

    return { loading, apiDetail };
};
