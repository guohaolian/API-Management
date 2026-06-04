import React, { useCallback, useMemo, useState } from "react";
import styles from "./index.module.less";
import { useSearchParams } from "react-router-dom";
import { useThisService, useServiceIteration } from "@/hooks/useService";
import useApi from "@/hooks/useApi";
import Detail from "./Detail";
import Header from "./Header";
import ApiList from "./ApiList";
import ApiEdit from "./ApiEdit";
import IterationAuditTimeline from "./IterationAuditTimeline";
import { Alert, Layout, Message, Spin } from "@cloud-materials/common";
import type { UserProfile } from "@/services/user/types";
import { inIterationWarning } from "@/utils";
import { ImportOpenapiToIteration } from "@/services/service";
import { resolveApiMessage } from "@/i18n/apiMessage";
import { t } from "i18next";

const ApiManagement: React.FC = () => {
    const [searchParams] = useSearchParams();
    const uuid = searchParams.get("uuid") || "";
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
        requiresIterationApproval,
        isServiceOwner,
        handleUpdateApprovalSetting,
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

    // 用于控制当前 API 相关逻辑
    const [selectedApiId, setSelectedApiId] = useState<number>(-1);

    const { loading: apiLoading, apiDetail } = useApi(
        selectedApiId,
        inIteration ? false : isLatest // 如果在迭代中，则 isLatest 为false
    );

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

    const [auditVisible, setAuditVisible] = useState(false);

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

    // 单独把loading抽离出来，为了让ApiList中Tree支持autoExpandParent
    // （autoExpandParent 仅在 Tree 第一次挂载的时候生效。如果数据是从远程获取，可以在数据获取完成后，再去渲染 Tree 组件）
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
                    isServiceOwner={isServiceOwner}
                    onUpdateApprovalSetting={handleUpdateApprovalSetting}
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
                        handleStartIteration,
                        handleCompleteIteration,
                        handleSubmitForApproval,
                        handleDirectPublish,
                        handleAddApi,
                        handleAddCategory,
                    }}
                />
            </Layout.Header>
            <Layout style={{ position: "relative" }}>
                {/* 左侧 API 列表 */}
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
                        treeData={
                            inIteration && iterationDetail
                                ? iterationTreeData
                                : treeData
                        }
                        setSelectedApiId={(id) => {
                            setSelectedApiId(id);
                        }}
                        handlers={{
                            handleUpdateApiCategory,
                            handleDeleteCategory: handleDeleteCategoryWithRefresh,
                        }}
                    />
                </Layout.Sider>
                <Layout.Content style={{ marginLeft: 300 }}>
                    {inIteration && iterationDetail ? (
                        <ApiEdit
                            loading={iterationLoading || apiLoading}
                            apiDetail={apiDetail}
                            readOnly={iterationReadOnly}
                            handlers={{
                                handleSaveApiDraft,
                                handleCopyApi,
                                handleDeleteApi,
                            }}
                        />
                    ) : (
                        <Detail loading={apiLoading} apiDetail={apiDetail} />
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

export default ApiManagement;
