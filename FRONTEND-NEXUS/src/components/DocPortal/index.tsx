import React, { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
    Alert,
    Button,
    Layout,
    Message,
    Select,
    Space,
    Spin,
    Tag,
    Typography,
} from "@cloud-materials/common";

import ApiList from "@/components/ApiManagement/ApiList";
import Detail from "@/components/ApiManagement/Detail";
import BlankPage from "@/components/shared/BlankPage";
import { useDocApiDetail, useDocPortal } from "@/hooks/useDocPortal";
import { DocsExportOpenapiByUuidAndVersion } from "@/services/docs";
import { copyToClipboard } from "@/utils";
import { toastFromError } from "@/i18n/apiMessage";
import styles from "./index.module.less";
import apiStyles from "@/components/ApiManagement/index.module.less";

const { Title, Paragraph } = Typography;

const DocPortal: React.FC = () => {
    const { t } = useTranslation();
    const [searchParams] = useSearchParams();
    const serviceUuid = searchParams.get("uuid") || "";
    const [selectedApiId, setSelectedApiId] = useState(-1);
    const [exportLoading, setExportLoading] = useState(false);

    const {
        loading,
        accessDenied,
        versions,
        currentVersion,
        setCurrentVersion,
        isLatest,
        docsPublic,
        serviceDescription,
        treeData,
    } = useDocPortal(serviceUuid);

    const { loading: apiLoading, apiDetail } = useDocApiDetail(
        selectedApiId,
        isLatest,
        currentVersion,
    );

    const hasApis = useMemo(
        () =>
            treeData.some(
                (group) => (group.children?.length ?? 0) > 0,
            ),
        [treeData],
    );

    const waitingForApiSelection = hasApis && selectedApiId <= 0;

    const handleVersionChange = (version: string) => {
        setSelectedApiId(-1);
        setCurrentVersion(version);
    };

    const portalUrl = useMemo(() => {
        if (!serviceUuid) return "";
        const params = new URLSearchParams({ uuid: serviceUuid });
        if (currentVersion) {
            params.set("version", currentVersion);
        }
        return `${window.location.origin}/portal?${params.toString()}`;
    }, [serviceUuid, currentVersion]);

    const handleExportOpenAPI = async () => {
        if (!serviceUuid || !currentVersion) return;
        setExportLoading(true);
        try {
            const res = await DocsExportOpenapiByUuidAndVersion(
                serviceUuid,
                currentVersion,
            );
            if (res.status !== 200 || !res.openapi_object) {
                throw new Error(res.message);
            }
            const blob = new Blob([JSON.stringify(res.openapi_object, null, 2)], {
                type: "application/json",
            });
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = `${serviceUuid.replace(/\//g, "_")}.json`;
            anchor.click();
            URL.revokeObjectURL(url);
        } catch (err: unknown) {
            Message.warning(toastFromError(err, "toast.exportOpenapiFailed"));
        } finally {
            setExportLoading(false);
        }
    };

    if (!serviceUuid) {
        return (
            <BlankPage
                message={t("docPortal.missingUuid")}
                description={t("docPortal.missingUuidHint")}
            />
        );
    }

    if (accessDenied && !loading) {
        return (
            <div className={styles.denied}>
                <BlankPage
                    message={t("docPortal.accessDenied")}
                    description={t("docPortal.accessDeniedHint")}
                />
            </div>
        );
    }

    return (
        <div className={styles.portalPage}>
            <div className={styles.portalHero}>
                <Space direction="vertical" size={4} style={{ flex: 1 }}>
                    <Space size={8} wrap>
                        <Title heading={4} style={{ margin: 0 }}>
                            {serviceUuid}
                        </Title>
                        {docsPublic ? (
                            <Tag color="green">{t("docPortal.publicBadge")}</Tag>
                        ) : (
                            <Tag color="orange">{t("docPortal.privatePreview")}</Tag>
                        )}
                    </Space>
                    {serviceDescription ? (
                        <Paragraph type="secondary" style={{ margin: 0 }}>
                            {serviceDescription}
                        </Paragraph>
                    ) : null}
                </Space>
                <Space wrap>
                    <Select
                        style={{ width: 140 }}
                        value={currentVersion || undefined}
                        onChange={handleVersionChange}
                        options={versions.map((v) => ({
                            label: v.is_latest
                                ? `${v.version} (${t("service.latestVersion")})`
                                : v.version,
                            value: v.version,
                        }))}
                    />
                    <Button
                        type="outline"
                        onClick={() => copyToClipboard(portalUrl)}
                    >
                        {t("docPortal.copyLink")}
                    </Button>
                    <Button
                        type="outline"
                        status="success"
                        loading={exportLoading}
                        onClick={handleExportOpenAPI}
                    >
                        {t("apiManagement.exportOpenapi")}
                    </Button>
                </Space>
            </div>

            <Alert
                type="info"
                content={t("docPortal.readOnlyHint")}
                style={{ marginBottom: 12 }}
            />

            {loading && !treeData.length ? (
                <div className={apiStyles.loadingCenter}>
                    <Spin dot />
                </div>
            ) : (
                <Layout className={apiStyles.apiPage}>
                    <Layout
                        className={styles.docWorkspace}
                        style={{ position: "relative" }}
                    >
                        <Layout.Sider
                            className={apiStyles.sidebar}
                            width={300}
                        >
                            <ApiList
                                inIteration={false}
                                isLatest={isLatest}
                                selectedApiId={selectedApiId}
                                treeData={treeData}
                                readOnly
                                handlers={{
                                    handleUpdateApiCategory: () => {},
                                    handleDeleteCategory: () => {},
                                }}
                                onSelectApi={setSelectedApiId}
                            />
                        </Layout.Sider>
                        <Layout.Content
                            className={styles.docContent}
                            style={{ marginLeft: 300 }}
                        >
                            {waitingForApiSelection ? (
                                <div className={apiStyles.loadingCenter}>
                                    <Spin dot />
                                </div>
                            ) : (
                                <Detail
                                    loading={apiLoading}
                                    apiDetail={apiDetail}
                                    isLatest={isLatest}
                                    serviceUuid={serviceUuid}
                                    currentVersion={currentVersion}
                                    showMock={false}
                                    emptyMessage={t("docPortal.noApis")}
                                />
                            )}
                        </Layout.Content>
                    </Layout>
                </Layout>
            )}
        </div>
    );
};

export default DocPortal;
