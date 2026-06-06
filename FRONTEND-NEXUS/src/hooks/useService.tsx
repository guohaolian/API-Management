import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
    CModal,
    Message,
    Typography,
    Space,
    Popover,
} from "@cloud-materials/common";
import { t } from "i18next";
import { useTranslation } from "react-i18next";
import { resolveApiMessage, toastFromError } from "@/i18n/apiMessage";

import {
    AddOrRemoveServiceMaintainerById,
    CommitIteration,
    CreateNewService,
    DeleteServiceById,
    ExportOpenapiByUuidAndVersion,
    GetAllDeletedServicesByUserId,
    GetAllServices,
    GetAllVersionsByUuid,
    GetHisNewestServicesByOwnerId,
    GetIterationById,
    GetMyMaintainedServices,
    GetMyNewestServices,
    GetServiceByUuidAndVersion,
    IsServiceMaintainer,
    RestoreServiceById,
    StartIteration,
    SubmitIterationForApproval,
    UpdateServiceApprovalSetting,
} from "@/services/service";
import { useUser } from "@/hooks/useUser";
import type {
    ApiBrief,
    ApiCategory,
    CreateNewServiceRequest,
    DeletedServiceItem,
    Pagination,
    ServiceDetail,
    ServiceItem,
    ServiceIterationDetail,
} from "@/services/service/types";
import CreateServiceForm from "@/components/ServiceManagement/CreateServiceForm";
import type { UserProfile } from "@/services/user/types";
import { genApiMethodTag } from "@/utils";
import AddCategoryForm from "@/components/ApiManagement/ApiList/AddCategoryForm";
import AddApiForm from "@/components/ApiManagement/ApiList/AddApiForm";

import {
    AddApi,
    AddCategoryByServiceId,
    CopyApiByApiDraftId,
    DeleteApiByApiDraftId,
    DeleteCategoryById,
    UpdateApiByApiDraftId,
    UpdateApiCategoryById,
} from "@/services/api";
import CompleteIterationForm, {
    incrementVersion,
} from "@/components/ApiManagement/ApiList/CompleteIterationForm";
import { markIterationPendingApproval } from "@/hooks/useIterationApprovalPolling";
import type {
    AddApiRequest,
    UpdateApiByApiDraftIdRequest,
    UpdateApiByApiDraftIdResponse,
} from "@/services/api/types";

const { Text, Ellipsis } = Typography;

const APPROVAL_SETTING_POLL_MS = 3_000;

// 服务列表hook
export const useService = () => {
    const navigate = useNavigate();

    const [serviceList, setServiceList] = useState<
        ServiceItem[] | DeletedServiceItem[]
    >([]);
    const [loading, setLoading] = useState(false);
    // 记录最近一次触发的获取服务操作，用于在删除、还原或新增服务后刷新列表
    const refetchRef = useRef<(() => Promise<number>) | null>(null);

    const fetchMyNewestServices = useCallback(
        async (pagination: Pagination) => {
            // 记录最近一次触发的获取服务操作，用于在删除或还原服务后刷新列表
            refetchRef.current = () => fetchMyNewestServices(pagination);

            setLoading(true);
            const res = await GetMyNewestServices(
                pagination.page_size,
                pagination.current_page,
            );
            if (res.status !== 200) {
                // 在这里不直接通过Message提示用户的原因是，在组件层一并捕获非200未成功和请求失败错误，一并处理
                setLoading(false);
                setServiceList([]);
                throw new Error(res.message || "获取服务失败");
            }
            setServiceList(res.services || []);
            setLoading(false);
            // 返回服务总数，用于分页
            return res.total || 0;
        },
        [],
    );

    const fetchMyMaintainedServices = useCallback(
        async (pagination: Pagination) => {
            // 记录最近一次触发的获取服务操作，用于在删除或还原服务后刷新列表
            refetchRef.current = () => fetchMyMaintainedServices(pagination);

            setLoading(true);
            const res = await GetMyMaintainedServices(
                pagination.page_size,
                pagination.current_page,
            );
            if (res.status !== 200) {
                setLoading(false);
                setServiceList([]);
                throw new Error(res.message || "获取服务失败");
            }
            setServiceList(res.services || []);
            setLoading(false);
            return res.total || 0;
        },
        [],
    );

    const fetchHisNewestServicesByOwnerId = useCallback(
        async (ownerId: number, pagination: Pagination) => {
            // 记录最近一次触发的获取服务操作，用于在删除或还原服务后刷新列表
            refetchRef.current = () =>
                fetchHisNewestServicesByOwnerId(ownerId, pagination);

            setLoading(true);
            const res = await GetHisNewestServicesByOwnerId(
                ownerId,
                pagination.page_size,
                pagination.current_page,
            );
            if (res.status !== 200) {
                setLoading(false);
                setServiceList([]);
                throw new Error(res.message || "获取服务失败");
            }
            setServiceList(res.services || []);
            setLoading(false);
            return res.total || 0;
        },
        [],
    );

    const fetchMyDeletedServices = useCallback(
        async (pagination: Pagination) => {
            // 记录最近一次触发的获取服务操作，用于在删除或还原服务后刷新列表
            refetchRef.current = () => fetchMyDeletedServices(pagination);

            setLoading(true);
            const res = await GetAllDeletedServicesByUserId(
                pagination.page_size,
                pagination.current_page,
            );
            if (res.status !== 200) {
                setLoading(false);
                setServiceList([]);
                throw new Error(res.message || "获取服务失败");
            }
            setServiceList(res.deleted_services || []);
            setLoading(false);
            return res.total || 0;
        },
        [],
    );

    const fetchAllServices = useCallback(async (pagination: Pagination) => {
        // 记录最近一次触发的获取服务操作，用于在删除或还原服务后刷新列表
        refetchRef.current = () => fetchAllServices(pagination);

        setLoading(true);
        const res = await GetAllServices(
            pagination.page_size,
            pagination.current_page,
        );
        if (res.status !== 200) {
            setLoading(false);
            setServiceList([]);
            throw new Error(res.message || "获取服务失败");
        }
        setServiceList(res.services || []);
        setLoading(false);
        return res.total || 0;
    }, []);

    const createNewService = useCallback(
        async (formData: CreateNewServiceRequest) => {
            const res = await CreateNewService(formData);
            if (res.status !== 200) {
                throw new Error(res.message || "创建服务失败");
            }
            return res;
        },
        [],
    );

    const handleViewService = useCallback(
        (service_uuid: string) => {
            navigate(`/service?uuid=${service_uuid}`);
        },
        [navigate],
    );

    const handleDeleteService = useCallback(async (id: number) => {
        setLoading(true);
        try {
            const res = await DeleteServiceById({ id });
            if (res.status !== 200) {
                setLoading(false);
                throw new Error(res.message || "删除服务失败");
            }
            Message.success(
                resolveApiMessage(res.message, "toast.deleteServiceSuccess"),
            );
            // 刷新服务列表
            await refetchRef.current?.();
        } catch (err) {
            Message.warning(toastFromError(err, "toast.deleteServiceFailed"));
        }
        setLoading(false);
    }, []);

    const handleRestoreService = useCallback(async (id: number) => {
        setLoading(true);
        const res = await RestoreServiceById({ id });
        if (res.status !== 200) {
            setLoading(false);
            throw new Error(res.message || "还原服务失败");
        }
        Message.success(
            resolveApiMessage(res.message, "toast.restoreServiceSuccess"),
        );
        // 刷新服务列表
        try {
            await refetchRef.current?.();
        } catch (err) {
            Message.warning(toastFromError(err, "toast.fetchServicesFailed"));
        }
        setLoading(false);
    }, []);

    const handleCreateService = useCallback(
        (owner?: UserProfile) => {
            const modal = CModal.openArcoForm({
                title: t("service.create"),
                content: <CreateServiceForm owner={owner} />,
                cancelText: t("common.cancel"),
                okText: t("service.submit"),
                onOk: async (values, form) => {
                    try {
                        await form.validate();
                        const res = await createNewService({
                            service_uuid: values.service_uuid,
                            description: values.description,
                        });
                        if (res.status !== 200) {
                            throw new Error(res.message || "服务创建失败");
                        }
                        Message.success(
                            resolveApiMessage(
                                res.message,
                                "toast.createServiceSuccess",
                            ),
                        );
                        // 显式关闭弹窗，避免依赖隐式行为
                        modal.close();
                        // 刷新服务列表
                        try {
                            await refetchRef.current?.();
                        } catch (err) {
                            Message.warning(
                                toastFromError(err, "toast.fetchServicesFailed"),
                            );
                        }
                    } catch (err: unknown) {
                        Message.warning(
                            toastFromError(err, "toast.createServiceFailed"),
                        );
                        // 抛出错误以阻止弹窗自动关闭（库内有相关处理）
                        throw err;
                    }
                },
            });
        },
        [createNewService],
    );

    return {
        serviceList,
        loading,
        fetchMyNewestServices,
        fetchMyMaintainedServices,
        fetchHisNewestServicesByOwnerId,
        fetchMyDeletedServices,
        fetchAllServices,
        createNewService,
        handleViewService,
        handleDeleteService,
        handleRestoreService,
        handleCreateService,
    };
};

// 某个服务hook
export const useThisService = (service_uuid: string) => {
    const navigate = useNavigate();
    const { user } = useUser();
    const { i18n } = useTranslation();

    const [loading, setLoading] = useState(false);
    const [versions, setVersions] = useState<
        {
            version: string;
            is_latest: boolean;
        }[]
    >([]);
    const [currentVersion, setCurrentVersion] = useState<string>("");
    const [isLatest, setIsLatest] = useState<boolean>(true);
    const [serviceDetail, setServiceDetail] = useState<
        ServiceDetail | ServiceIterationDetail
    >({} as ServiceDetail);
    const [apiCategories, setApiCategories] = useState<ApiCategory[]>([]);
    const [apis, setApis] = useState<ApiBrief[]>([]);
    const [inIteration, setInIteration] = useState(false);
    const [iterationId, setIterationId] = useState<number>(-1);

    const fetchAllVersions = useCallback(async () => {
        setLoading(true);
        try {
            const res = await GetAllVersionsByUuid(service_uuid);
            if (res.status !== 200) {
                setLoading(false);
                setVersions([]);
                throw new Error(res.message || "获取版本失败");
            }
            setVersions(res.versions.filter((v) => v.version) || []); // 筛选掉正在迭代的，没有版本号的service_iteration
            const latestVersion = res.versions?.[0]?.version || "";
            setCurrentVersion(latestVersion);
            setIsLatest(res.versions?.[0]?.is_latest || false);
            return latestVersion;
        } catch (err: unknown) {
            Message.warning(toastFromError(err, "toast.fetchVersionsFailed"));
            navigate("/");
            return "";
        } finally {
            setLoading(false);
        }
    }, [service_uuid, navigate]);

    useEffect(() => {
        fetchAllVersions();
    }, [fetchAllVersions]);

    const fetchServiceDetail = useCallback(
        async (version: string) => {
            setLoading(true);
            try {
                const res = await GetServiceByUuidAndVersion(
                    service_uuid,
                    version,
                );
                if (res.status !== 200) {
                    setServiceDetail({} as ServiceDetail);
                    throw new Error(res.message || "获取服务详情失败");
                }
                setServiceDetail(res.service || {});
                setIsLatest(res.is_latest);
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
                Message.warning(
                    toastFromError(err, "toast.fetchServiceDetailFailed"),
                );
            } finally {
                setLoading(false);
            }
        },
        [service_uuid],
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
                            style={{
                                color: "#6e7687",
                                fontSize: 10,
                            }}
                            rows={1}
                            showTooltip
                        >
                            {api.path}
                        </Ellipsis>
                    </Space>
                ),
                style: {
                    maxWidth: "100%",
                    overflow: "auto",
                    scrollbarWidth: "none",
                },
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
    }, [apiCategories, apis, i18n.language]);

    const handleAddCategory = useCallback(() => {
        const modal = CModal.openArcoForm({
            title: t("category.add"),
            content: <AddCategoryForm />,
            cancelText: t("common.cancel"),
            okText: t("common.ok"),
            onOk: async (values, form) => {
                try {
                    await form.validate();
                    const res = await AddCategoryByServiceId({
                        service_id: serviceDetail.id,
                        category_name: values.category_name,
                        description: values.description,
                    });
                    if (res.status !== 200) {
                        throw new Error(res.message || "分类添加失败");
                    }
                    Message.success(
                        resolveApiMessage(res.message, "toast.addCategorySuccess"),
                    );
                    // 显式关闭弹窗，避免依赖隐式行为
                    modal.close();
                    setApiCategories((prev) => [...prev, res.category || {}]);
                } catch (err: unknown) {
                    Message.warning(
                        toastFromError(err, "toast.addCategoryFailed"),
                    );
                    // 抛出错误以阻止弹窗自动关闭（库内有相关处理）
                    throw err;
                }
            },
        });
    }, [serviceDetail.id, currentVersion, fetchServiceDetail]);

    const handleUpdateApiCategory = useCallback(
        async (api_id: number, category_id: number) => {
            try {
                const res = await UpdateApiCategoryById({
                    api_id,
                    category_id,
                });
                if (res.status !== 200) {
                    throw new Error(res.message || "API 分类更新失败");
                }
                setApis((prev) =>
                    prev.map((api) =>
                        api.id === api_id
                            ? {
                                  ...api,
                                  category_id:
                                      category_id >= 0 ? category_id : null,
                              }
                            : api,
                    ),
                );
            } catch (err: unknown) {
                Message.warning(
                    toastFromError(err, "toast.updateApiCategoryFailed"),
                );
                throw err;
            }
        },
        [currentVersion, fetchServiceDetail],
    );

    const handleDeleteCategory = useCallback(
        async (category_id: number) => {
            try {
                const payload: Parameters<typeof DeleteCategoryById>[0] = {
                    category_id,
                };
                if (inIteration && iterationId > 0) {
                    payload.service_iteration_id = iterationId;
                }
                const res = await DeleteCategoryById(payload);
                if (res.status !== 200) {
                    throw new Error(res.message || "分类删除失败");
                }
                Message.success(
                    resolveApiMessage(
                        res.message,
                        "toast.deleteCategorySuccess",
                    ),
                );
                setApiCategories((prev) =>
                    prev.filter((cat) => cat.id !== category_id),
                );
                return true;
            } catch (err: unknown) {
                Message.warning(
                    toastFromError(err, "toast.deleteCategoryFailed"),
                );
                return false;
            }
        },
        [currentVersion, fetchServiceDetail, inIteration, iterationId],
    );

    const checkIsServiceMaintainer = useCallback(
        async (candidate_id: number) => {
            try {
                const res = await IsServiceMaintainer({
                    service_id: serviceDetail.id,
                    candidate_id,
                });
                if (res.status !== 200) {
                    throw new Error(res.message || "服务维护者检查失败");
                }
                return res.is_current_maintainer;
            } catch (err: unknown) {
                Message.warning(
                    toastFromError(err, "toast.checkMaintainerFailed"),
                );
                return false;
            }
        },
        [serviceDetail.id],
    );

    const handleAddOrRemoveServiceMaintainerById = useCallback(
        async (candidate_id: number) => {
            try {
                const res = await AddOrRemoveServiceMaintainerById({
                    service_id: serviceDetail.id,
                    candidate_id,
                });
                if (res.status !== 200) {
                    throw new Error(res.message || "服务维护者操作失败");
                }
                Message.success(
                    resolveApiMessage(res.message, "toast.maintainerOpSuccess"),
                );
                return res.is_current_maintainer;
            } catch (err: unknown) {
                Message.warning(
                    toastFromError(err, "toast.maintainerOpFailed"),
                );
                return false;
            }
        },
        [serviceDetail.id, currentVersion, fetchServiceDetail],
    );

    const handleExportOpenAPI = useCallback(async () => {
        try {
            const res = await ExportOpenapiByUuidAndVersion(
                service_uuid,
                currentVersion,
            );
            console.log(res);
            if (res.status !== 200) {
                throw new Error(res.message || "导出 OpenAPI 失败");
            }
            return res.openapi_object;
        } catch (err: unknown) {
            Message.warning(toastFromError(err, "toast.exportOpenapiFailed"));
            return null;
        }
    }, [service_uuid, currentVersion]);

    const handleStartIteration = useCallback(async () => {
        try {
            const res = await StartIteration({
                service_id: serviceDetail.id,
            });
            if (res.status !== 200 && res.status !== 201) {
                throw new Error(res.message || "迭代开始失败");
            }
            Message.success(
                resolveApiMessage(res.message, "toast.startIterationSuccess"),
            );
            setInIteration(true);
            setIterationId(res.service_iteration_id);
        } catch (err: unknown) {
            Message.warning(toastFromError(err, "toast.startIterationFailed"));
        }
    }, [serviceDetail.id, currentVersion, fetchServiceDetail]);

    const serviceMeta = useMemo((): ServiceDetail => {
        if ("service_uuid" in serviceDetail && "owner_id" in serviceDetail) {
            return serviceDetail as ServiceDetail;
        }
        const iter = serviceDetail as ServiceIterationDetail;
        const nested = iter.service;
        return {
            id: nested?.id ?? iter.service_id,
            owner_id: nested?.owner_id ?? 0,
            service_uuid: nested?.service_uuid ?? service_uuid,
            version: nested?.version ?? iter.version ?? "",
            description: nested?.description ?? iter.description,
            created_at: nested?.created_at ?? "",
            is_deleted: nested?.is_deleted ?? false,
            requires_iteration_approval:
                nested?.requires_iteration_approval ?? false,
        };
    }, [serviceDetail, service_uuid]);

    const serviceId = serviceMeta.id;
    const requiresIterationApproval =
        !!serviceMeta.requires_iteration_approval;
    const isServiceOwner =
        serviceMeta.owner_id === user?.id || user?.level === 0;

    const applyRequiresIterationApproval = useCallback((enabled: boolean) => {
        setServiceDetail((prev) => {
            if ("requires_iteration_approval" in prev) {
                if (prev.requires_iteration_approval === enabled) return prev;
                return { ...prev, requires_iteration_approval: enabled };
            }
            if ("service" in prev && prev.service) {
                if (prev.service.requires_iteration_approval === enabled) {
                    return prev;
                }
                return {
                    ...prev,
                    service: {
                        ...prev.service,
                        requires_iteration_approval: enabled,
                    },
                };
            }
            return prev;
        });
    }, []);

    const syncApprovalSettingFromServer = useCallback(async (): Promise<
        boolean | null
    > => {
        try {
            if (iterationId > 0) {
                const res = await GetIterationById(iterationId);
                if (res.status === 200 && res.iteration?.service) {
                    const enabled =
                        !!res.iteration.service.requires_iteration_approval;
                    applyRequiresIterationApproval(enabled);
                    return enabled;
                }
            }
            if (!service_uuid || !currentVersion) {
                return null;
            }
            const res = await GetServiceByUuidAndVersion(
                service_uuid,
                currentVersion,
            );
            if (res.status !== 200 || !res.service) {
                return null;
            }
            const service = res.service;
            const nested =
                "requires_iteration_approval" in service
                    ? service
                    : "service" in service
                      ? service.service
                      : undefined;
            const enabled = !!nested?.requires_iteration_approval;
            applyRequiresIterationApproval(enabled);
            return enabled;
        } catch {
            return null;
        }
    }, [
        iterationId,
        service_uuid,
        currentVersion,
        applyRequiresIterationApproval,
    ]);

    useEffect(() => {
        if (!inIteration || iterationId <= 0) {
            return;
        }

        void syncApprovalSettingFromServer();

        const timer = window.setInterval(() => {
            void syncApprovalSettingFromServer();
        }, APPROVAL_SETTING_POLL_MS);

        const refreshOnFocus = () => {
            void syncApprovalSettingFromServer();
        };
        const refreshOnVisible = () => {
            if (document.visibilityState === "visible") {
                void syncApprovalSettingFromServer();
            }
        };
        window.addEventListener("focus", refreshOnFocus);
        document.addEventListener("visibilitychange", refreshOnVisible);

        return () => {
            window.clearInterval(timer);
            window.removeEventListener("focus", refreshOnFocus);
            document.removeEventListener("visibilitychange", refreshOnVisible);
        };
    }, [inIteration, iterationId, syncApprovalSettingFromServer]);

    const resolveApprovalRequired = useCallback(async () => {
        const fresh = await syncApprovalSettingFromServer();
        return fresh ?? requiresIterationApproval;
    }, [syncApprovalSettingFromServer, requiresIterationApproval]);

    const runCompleteIterationForm = useCallback(
        (
            mode: "commit" | "submit" | "auto",
            titleKey: string,
            successToastKey: string,
            failToastKey: string,
        ) => {
            let serverLatestVersion = currentVersion;
            const openForm = async () => {
                try {
                    const res = await GetAllVersionsByUuid(service_uuid);
                    if (res.status === 200 && res.versions?.[0]?.version) {
                        serverLatestVersion = res.versions[0].version;
                    }
                } catch {
                    /* use local version */
                }

                const suggestedFromLocal = incrementVersion(currentVersion);
                const hasVersionConflict =
                    !!suggestedFromLocal &&
                    suggestedFromLocal === serverLatestVersion;

                const modal = CModal.openArcoForm({
                    title: t(titleKey),
                    content: (
                        <CompleteIterationForm
                            currentVersion={
                                hasVersionConflict
                                    ? serverLatestVersion
                                    : currentVersion
                            }
                            initialNewVersion={
                                hasVersionConflict
                                    ? incrementVersion(serverLatestVersion)
                                    : suggestedFromLocal
                            }
                            versionConflict={hasVersionConflict}
                            conflictServerVersion={
                                hasVersionConflict
                                    ? serverLatestVersion
                                    : undefined
                            }
                        />
                    ),
                    cancelText: t("common.cancel"),
                    okText: t("common.ok"),
                    onOk: async (values, form) => {
                        try {
                            await form.validate();
                            let resolvedMode = mode;
                            if (mode === "auto") {
                                const fresh =
                                    await syncApprovalSettingFromServer();
                                resolvedMode =
                                    (fresh ?? requiresIterationApproval)
                                        ? "submit"
                                        : "commit";
                            }
                            const payload = {
                                service_iteration_id: iterationId,
                                new_version: values.new_version,
                            };
                            const res =
                                resolvedMode === "submit"
                                    ? await SubmitIterationForApproval(payload)
                                    : await CommitIteration(payload);
                            if (res.status !== 200) {
                                throw new Error(res.message);
                            }
                            Message.success(
                                resolveApiMessage(res.message, successToastKey),
                            );
                            if (resolvedMode === "submit") {
                                markIterationPendingApproval(
                                    service_uuid,
                                    iterationId,
                                );
                            }
                            modal.close();
                            setTimeout(() => {
                                window.location.reload();
                            }, 500);
                        } catch (err: unknown) {
                            Message.warning(toastFromError(err, failToastKey));
                            throw err;
                        }
                    },
                });
            };
            return openForm();
        },
        [
            iterationId,
            currentVersion,
            service_uuid,
            syncApprovalSettingFromServer,
            requiresIterationApproval,
        ],
    );

    const handleSubmitForApproval = useCallback(async () => {
        await runCompleteIterationForm(
            "auto",
            "approval.submitTitle",
            "approval.submitSuccess",
            "approval.submitFailed",
        );
    }, [runCompleteIterationForm]);

    const handleDirectPublish = useCallback(async () => {
        CModal.confirm({
            title: t("approval.directPublishConfirmTitle"),
            content: t("approval.directPublishConfirmContent"),
            okText: t("approval.directPublish"),
            cancelText: t("common.cancel"),
            onOk: () =>
                runCompleteIterationForm(
                    "commit",
                    "iteration.complete",
                    "toast.commitIterationSuccess",
                    "toast.commitIterationFailed",
                ),
        });
    }, [runCompleteIterationForm]);

    const handleCompleteIteration = useCallback(async () => {
        const needsApproval = await resolveApprovalRequired();
        await runCompleteIterationForm(
            "auto",
            needsApproval ? "approval.submitTitle" : "iteration.complete",
            needsApproval ? "approval.submitSuccess" : "toast.commitIterationSuccess",
            needsApproval ? "approval.submitFailed" : "toast.commitIterationFailed",
        );
    }, [resolveApprovalRequired, runCompleteIterationForm]);

    const handleUpdateApprovalSetting = useCallback(
        async (enabled: boolean) => {
            if (!serviceId) return false;
            try {
                const res = await UpdateServiceApprovalSetting({
                    service_id: serviceId,
                    requires_iteration_approval: enabled,
                });
                if (res.status !== 200) {
                    throw new Error(res.message);
                }
                setServiceDetail((prev) => {
                    if ("requires_iteration_approval" in prev) {
                        return { ...prev, requires_iteration_approval: enabled };
                    }
                    if ("service" in prev && prev.service) {
                        return {
                            ...prev,
                            service: {
                                ...prev.service,
                                requires_iteration_approval: enabled,
                            },
                        };
                    }
                    return prev;
                });
                Message.success(
                    resolveApiMessage(res.message, "approval.settingSuccess"),
                );
                return true;
            } catch (err: unknown) {
                Message.warning(
                    toastFromError(err, "approval.settingFailed"),
                );
                return false;
            }
        },
        [serviceId],
    );

    const exitIteration = () => {
        setInIteration(false);
        setIterationId(-1);
    };

    const resumeIteration = useCallback((id: number) => {
        setInIteration(true);
        setIterationId(id);
    }, []);

    return {
        loading,
        versions,
        currentVersion,
        isLatest,
        serviceDetail,
        apiCategories,
        apis,
        treeData,
        inIteration,
        iterationId,
        setCurrentVersion,
        handleAddCategory,
        handleUpdateApiCategory,
        handleDeleteCategory,
        checkIsServiceMaintainer,
        handleAddOrRemoveServiceMaintainerById,
        handleExportOpenAPI,
        setInIteration,
        handleStartIteration,
        handleCompleteIteration,
        handleSubmitForApproval,
        handleDirectPublish,
        exitIteration,
        resumeIteration,
        fetchAllVersions,
        fetchServiceDetail,
        requiresIterationApproval,
        isServiceOwner,
        handleUpdateApprovalSetting,
    };
};

// 迭代相关（只用于一次迭代周期内，与服务历史版本无关）
export const useServiceIteration = (
    iterationId: number,
    apiCategories: ApiCategory[],
) => {
    const { i18n } = useTranslation();
    const [loading, setLoading] = useState(false);
    const [iterationDetail, setIterationDetail] =
        useState<ServiceIterationDetail>({} as ServiceIterationDetail);
    const [apiDrafts, setApiDrafts] = useState<ApiBrief[]>([]);

    const fetchIterationDetail = useCallback(async () => {
        if (iterationId <= 0) return;
        setLoading(true);
        try {
            const res = await GetIterationById(iterationId);
            if (res.status !== 200) {
                setIterationDetail({} as ServiceIterationDetail);
                throw new Error(res.message || "获取当前迭代详情失败");
            }
            setIterationDetail(res.iteration || {});
            if ("api_drafts" in res.iteration) {
                setApiDrafts(res.iteration.api_drafts || [] || []);
            }
        } catch (err: unknown) {
            Message.warning(
                toastFromError(err, "toast.fetchIterationDetailFailed"),
            );
        } finally {
            setLoading(false);
        }
    }, [iterationId]);

    useEffect(() => {
        fetchIterationDetail();
    }, [fetchIterationDetail]);

    const iterationTreeData = useMemo(() => {
        if (!apiCategories || !apiDrafts) {
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

        apiDrafts
            .sort((a, b) => a.method.localeCompare(b.method))
            .forEach((apiDraft) => {
                const node = {
                    key: apiDraft.id.toString(),
                    searchText: `${apiDraft.method} ${apiDraft.name} ${apiDraft.path}`.toLowerCase(),
                    title: (
                        <Space style={{ fontWeight: 500 }}>
                            {genApiMethodTag(apiDraft.method, "small")}
                            {apiDraft.name}
                            <Ellipsis
                                style={{
                                    color: "#6e7687",
                                    fontSize: 10,
                                    maxWidth: 160,
                                }}
                                rows={1}
                                showTooltip
                            >
                                {apiDraft.path}
                            </Ellipsis>
                        </Space>
                    ),
                    style: {
                        maxWidth: "100%",
                        overflow: "auto",
                        scrollbarWidth: "none",
                    },
                };
                if (apiDraft.category_id == null) {
                    uncategorizedGroup.children.push(node);
                } else {
                    const group = categoryMap.get(apiDraft.category_id);
                    if (group) {
                        group.children.push(node);
                    } else {
                        uncategorizedGroup.children.push(node);
                    }
                }
            });

        return [...Array.from(categoryMap.values()), uncategorizedGroup];
    }, [apiCategories, apiDrafts, i18n.language]);

    const handleAddApi = useCallback(() => {
        const modal = CModal.openArcoForm({
            title: t("apiManagement.addApi"),
            content: <AddApiForm apiCategories={apiCategories} />,
            cancelText: t("common.cancel"),
            okText: t("common.ok"),
            onOk: async (values, form) => {
                try {
                    await form.validate();
                    let data: AddApiRequest = {
                        service_iteration_id: iterationId,
                        name: values.name,
                        method: values.method,
                        path: values.path,
                        description: values?.description || "",
                        level: values.level || "P2",
                    };
                    if (values.category_id > 0) {
                        data.category_id = values.category_id;
                    }
                    const res = await AddApi(data);
                    if (res.status !== 200) {
                        throw new Error(res.message || "API 添加失败");
                    }
                    Message.success(
                        resolveApiMessage(res.message, "toast.addApiSuccess"),
                    );
                    // 显式关闭弹窗，避免依赖隐式行为
                    modal.close();
                    // 刷新
                    /* 
                        这里应当加await：
                        1. 异步函数 ： fetchIterationDetail 是一个 async 函数（定义在第 595 行），它返回一个 Promise。
                        2. 执行顺序 ：加上 await 可以确保在 onOk 函数结束前，数据刷新操作已经完成。虽然在此处弹窗已经关闭（ modal.close() ），但等待刷新完成可以保证后续逻辑（如果有）是在数据更新后执行的。
                        3. 代码规范 ：在 async 函数中调用另一个 async 函数时，通常建议使用 await ，除非明确希望“触发即忘”（Fire-and-forget）。这有助于避免潜在的竞态条件，并使执行流程更清晰。
                    */
                    await fetchIterationDetail();
                } catch (err: unknown) {
                    Message.warning(toastFromError(err, "toast.addApiFailed"));
                    // 抛出错误以阻止弹窗自动关闭（库内有相关处理）
                    throw err;
                }
            },
        });
    }, [iterationId, fetchIterationDetail]);

    const handleCopyApi = useCallback(
        async (apiDraftId: number) => {
            const res = await CopyApiByApiDraftId({
                service_iteration_id: iterationId,
                api_draft_id: apiDraftId,
            });
            if (res.status !== 200) {
                throw new Error(res.message || "API 复制失败");
            }
            Message.success(
                resolveApiMessage(res.message, "toast.copyApiSuccess"),
            );
            // 刷新
            await fetchIterationDetail();
        },
        [iterationId, fetchIterationDetail],
    );

    const handleDeleteApi = useCallback(
        async (apiDraftId: number) => {
            const res = await DeleteApiByApiDraftId({
                service_iteration_id: iterationId,
                api_draft_id: apiDraftId,
            });
            if (res.status !== 200) {
                throw new Error(res.message || "API 删除失败");
            }
            Message.success(
                resolveApiMessage(res.message, "toast.deleteApiSuccess"),
            );
            // 刷新
            await fetchIterationDetail();
        },
        [iterationId, fetchIterationDetail],
    );

    const handleSaveApiDraft = useCallback(
        async (
            data: Omit<UpdateApiByApiDraftIdRequest, "service_iteration_id">,
        ): Promise<UpdateApiByApiDraftIdResponse> => {
            const res = await UpdateApiByApiDraftId({
                ...data,
                service_iteration_id: iterationId,
            });
            if (res.status !== 200) {
                throw new Error(res.message || "API 保存失败");
            }
            // 刷新
            await fetchIterationDetail();
            return res;
        },
        [iterationId, fetchIterationDetail],
    );

    const iterationApprovalStatus = iterationDetail.approval_status;
    const iterationReadOnly = iterationApprovalStatus === "pending";

    return {
        loading,
        iterationDetail,
        apiDrafts,
        iterationTreeData,
        iterationApprovalStatus,
        iterationReadOnly,
        fetchIterationDetail,
        handleAddApi,
        handleCopyApi,
        handleDeleteApi,
        handleSaveApiDraft,
    };
};
