import React, { useCallback, useEffect, useMemo, useState } from "react";
import styles from "../index.module.less";
import { useThisService, useServiceIteration } from "@/hooks/useService";
import { useIterationApprovalPolling } from "@/hooks/useIterationApprovalPolling";
import useApi from "@/hooks/useApi";
import Detail from "../Detail";
import Header from "../layout/Header";
import ApiList from "../ApiList";
import ApiEdit from "../ApiEdit";
import IterationAuditTimeline from "../modals/IterationAuditTimeline";
import { Alert, Layout, Message, Modal, Spin } from "@cloud-materials/common";
import type { UserProfile } from "@/services/user/types";
import { inIterationWarning } from "@/utils";
import { ImportOpenapiToIteration } from "@/services/service";
import { resolveApiMessage } from "@/i18n/apiMessage";
import { t } from "i18next";

const ApiManagementDetail: React.FC<{ uuid: string }> = ({ uuid }) => {
    const {
        loading,
        versions,
        currentVersion,
        isLatest,
        serviceDetail,
        apiCategories,
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
        docsPublic,
        handleUpdateDocsPublicSetting,
    } = useThisService(uuid);

    const serviceUuid = useMemo(() => {
        return "service_uuid" in serviceDetail
            ? serviceDetail.service_uuid
            : serviceDetail?.service?.service_uuid || "";
    }, [serviceDetail]);

    const personInCharge = useMemo(() => {
        return "owner" in serviceDetail
            ? (serviceDetail.owner as UserProfile)
            : "creator" in serviceDetail
            ? (serviceDetail.creator as UserProfile)
            : ({} as UserProfile);
    }, [serviceDetail]);

    const [selectedApiId, setSelectedApiId] = useState<number>(-1);
    const [apiHasUnsavedChanges, setApiHasUnsavedChanges] = useState(false);

    const {
        loading: iterationLoading,
        iterationDetail,
        iterationTreeData,
        fetchIterationDetail,
        handleAddApi,
        handleSaveApiDraft,
        handleCopyApi,
        handleDeleteApi,
        iterationApprovalStatus,
        iterationReadOnly,
    } = useServiceIteration(iterationId, apiCategories);

    const iterationTreeReady =
        inIteration && iterationId > 0 && iterationDetail?.id === iterationId;

    useEffect(() => {
        if (inIteration) {
            setSelectedApiId(-1);
            setApiHasUnsavedChanges(false);
        }
    }, [inIteration, iterationId]);

    const handleApiDirtyChange = useCallback((dirty: boolean) => {
        setApiHasUnsavedChanges(dirty);
    }, []);

    const blockIfUnsavedApi = useCallback(
        (messageKey: string) => {
            if (
                iterationTreeReady &&
                apiHasUnsavedChanges &&
                selectedApiId > 0
            ) {
                Modal.warning({
                    title: t("common.notice"),
                    content: t(messageKey),
                    okText: t("common.ok"),
                });
                return true;
            }
            return false;
        },
        [iterationTreeReady, apiHasUnsavedChanges, selectedApiId],
    );

    const guardIterationCompleteAction = useCallback(
        (action: () => void | Promise<void>) => {
            if (blockIfUnsavedApi("iteration.unsavedApiBeforeComplete")) {
                return;
            }
            void action();
        },
        [blockIfUnsavedApi],
    );

    const handleRequestSelectApi = useCallback(
        (apiId: number) => {
            if (apiId === selectedApiId) {
                return;
            }
            if (blockIfUnsavedApi("iteration.unsavedApiSwitchBlocked")) {
                return;
            }
            setSelectedApiId(apiId);
        },
        [selectedApiId, blockIfUnsavedApi],
    );

    const handleSaveApiDraftWithClearDirty = useCallback(
        async (
            data: Parameters<typeof handleSaveApiDraft>[0],
        ) => {
            const res = await handleSaveApiDraft(data);
            setApiHasUnsavedChanges(false);
            return res;
        },
        [handleSaveApiDraft],
    );

    const { loading: apiLoading, apiDetail } = useApi(
        selectedApiId,
        iterationTreeReady ? false : isLatest,
    );

    const [auditVisible, setAuditVisible] = useState(false);

    const handleApprovalApproved = useCallback(async () => {
        exitIteration();
        const latestVersion = await fetchAllVersions();
        if (latestVersion) {
            await fetchServiceDetail(latestVersion);
        }
    }, [exitIteration, fetchAllVersions, fetchServiceDetail]);

    const handleApprovalRejected = useCallback(
        (id: number) => {
            if (inIteration && iterationId === id) {
                void fetchIterationDetail();
                return;
            }
            resumeIteration(id);
        },
        [resumeIteration, fetchIterationDetail, inIteration, iterationId],
    );

    useIterationApprovalPolling({
        serviceUuid: serviceUuid || uuid,
        inIteration,
        iterationId,
        iterationApprovalStatus,
        onApproved: handleApprovalApproved,
        onRejected: handleApprovalRejected,
    });

    const handleImportOpenAPI = useCallback(
        async (openapiObject: Record<string, any>) => {
            if (!inIteration || iterationId <= 0) {
                Message.warning(t("toast.startIterationFirst"));
                return;
            }
            const res = await ImportOpenapiToIteration({
                service_iteration_id: iterationId,
                openapi_object: openapiObject,
            });
            if (res.status !== 200) {
                throw new Error(res.message || "导入 OpenAPI 失败");
            }
            Message.success(
                resolveApiMessage(res.message, "toast.importOpenapiSuccess"),
            );
            await fetchIterationDetail();
        },
        [inIteration, iterationId, fetchIterationDetail],
    );

    const handleDeleteCategoryWithRefresh = useCallback(
        async (categoryId: number) => {
            const ok = await handleDeleteCategory(categoryId);
            if (ok && inIteration) {
                setSelectedApiId(-1);
                setApiHasUnsavedChanges(false);
                await fetchIterationDetail();
            }
        },
        [handleDeleteCategory, inIteration, fetchIterationDetail],
    );

    const isLoading =
        loading ||
        !versions ||
        !serviceUuid ||
        !treeData ||
        treeData.length === 0;

    if (isLoading) {
        return (
            <div className={styles.loadingCenter}>
                <Spin dot />
            </div>
        );
    }

    return (
        <Layout className={styles.apiPage}>
            <Layout.Header>
                <Header
                    loading={loading}
                    serviceUuid={serviceUuid}
                    versions={versions}
                    isLatest={isLatest}
                    currentVersion={currentVersion}
                    personInCharge={personInCharge}
                    maintainers={
                        "maintainers" in serviceDetail
                            ? (serviceDetail.maintainers as UserProfile[])
                            : []
                    }
                    inIteration={inIteration}
                    iterationReadOnly={iterationReadOnly}
                    iterationApprovalStatus={iterationApprovalStatus}
                    requiresIterationApproval={requiresIterationApproval}
                    docsPublic={docsPublic}
                    isServiceOwner={isServiceOwner}
                    onUpdateApprovalSetting={handleUpdateApprovalSetting}
                    onUpdateDocsPublicSetting={handleUpdateDocsPublicSetting}
                    onOpenAudit={
                        inIteration && iterationId > 0
                            ? () => setAuditVisible(true)
                            : undefined
                    }
                    handlers={{
                        setCurrentVersion: (v) =>
                            inIterationWarning(
                                () => {
                                    setSelectedApiId(-1);
                                    setCurrentVersion(v);
                                },
                                inIteration,
                                "reject"
                            ),
                        exitIteration,
                        checkIsServiceMaintainer,
                        handleAddOrRemoveServiceMaintainerById,
                        handleExportOpenAPI,
                        handleImportOpenAPI,
                        handleStartIteration: async () => {
                            setSelectedApiId(-1);
                            await handleStartIteration();
                        },
                        handleCompleteIteration: () =>
                            guardIterationCompleteAction(
                                handleCompleteIteration,
                            ),
                        handleSubmitForApproval: () =>
                            guardIterationCompleteAction(
                                handleSubmitForApproval,
                            ),
                        handleDirectPublish: () =>
                            guardIterationCompleteAction(
                                handleDirectPublish,
                            ),
                        handleAddApi,
                        handleAddCategory,
                    }}
                />
            </Layout.Header>
            <Layout style={{ position: "relative" }}>
                <Layout.Sider className={styles.sidebar} width={300}>
                    {inIteration &&
                        iterationApprovalStatus === "rejected" &&
                        iterationDetail.review_comment && (
                            <Alert
                                type="error"
                                content={iterationDetail.review_comment}
                                title={t("approval.rejectedBanner")}
                                style={{ margin: "8px 12px" }}
                            />
                        )}
                    {inIteration && iterationApprovalStatus === "pending" && (
                        <Alert
                            type="warning"
                            content={t("approval.pendingBanner")}
                            style={{ margin: "8px 12px" }}
                        />
                    )}
                    {inIteration &&
                        isLatest &&
                        isServiceOwner &&
                        !requiresIterationApproval && (
                            <Alert
                                type="info"
                                content={t("approval.enableSwitchHint")}
                                style={{ margin: "8px 12px" }}
                            />
                        )}
                    <ApiList
                        inIteration={inIteration}
                        isLatest={isLatest}
                        autoSelectFirst={!inIteration || iterationTreeReady}
                        selectedApiId={selectedApiId}
                        treeData={
                            iterationTreeReady ? iterationTreeData : treeData
                        }
                        onSelectApi={handleRequestSelectApi}
                        handlers={{
                            handleUpdateApiCategory,
                            handleDeleteCategory: handleDeleteCategoryWithRefresh,
                        }}
                    />
                </Layout.Sider>
                <Layout.Content style={{ marginLeft: 300 }}>
                    {iterationTreeReady ? (
                        <ApiEdit
                            loading={iterationLoading || apiLoading}
                            detailLoading={apiLoading}
                            apiDetail={apiDetail}
                            readOnly={iterationReadOnly}
                            serviceUuid={uuid}
                            currentVersion={currentVersion}
                            serviceIterationId={iterationId}
                            onDirtyChange={handleApiDirtyChange}
                            handlers={{
                                handleSaveApiDraft: handleSaveApiDraftWithClearDirty,
                                handleCopyApi,
                                handleDeleteApi,
                            }}
                        />
                    ) : inIteration ? (
                        <div className={styles.loadingCenter}>
                            <Spin dot />
                        </div>
                    ) : (
                        <Detail
                            loading={apiLoading}
                            apiDetail={apiDetail}
                            isLatest={isLatest}
                            serviceUuid={uuid}
                            currentVersion={currentVersion}
                        />
                    )}
                </Layout.Content>
            </Layout>
            {inIteration && iterationId > 0 && (
                <IterationAuditTimeline
                    serviceIterationId={iterationId}
                    visible={auditVisible}
                    onClose={() => setAuditVisible(false)}
                />
            )}
        </Layout>
    );
};

export default ApiManagementDetail;
