import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
    Button,
    Message,
    Modal,
    Select,
    Space,
    Spin,
    Table,
    Tag,
    Typography,
} from "@cloud-materials/common";
import Collapse from "@arco-design/web-react/es/Collapse";
import Empty from "@arco-design/web-react/es/Empty";
import type { HttpMethod } from "@/services/api/types";
import { useTranslation } from "react-i18next";
import {
    CompareVersionsByUuid,
    GetIterationChangePreview,
} from "@/services/service";
import type {
    CompareVersionsByUuidResponse,
    FieldChange,
    ModifiedApiDiff,
    ParamDiffEntry,
} from "@/services/service/types";
import { toastFromError } from "@/i18n/apiMessage";
import { genApiMethodTag } from "@/utils";

const { Text, Paragraph } = Typography;
const CollapseItem = Collapse.Item;

interface VersionDiffModalProps {
    visible: boolean;
    serviceUuid: string;
    versions: { version: string; is_latest: boolean }[];
    currentVersion: string;
    onClose: () => void;
    /** 迭代变更预览：传入后自动拉取草稿 vs 基线 diff，隐藏版本选择器 */
    serviceIterationId?: number;
}

const fieldChangeColumns = (t: (key: string) => string) => [
    { title: t("versionDiff.field"), dataIndex: "field", width: 120 },
    {
        title: t("versionDiff.oldValue"),
        dataIndex: "old",
        render: (v: unknown) => (
            <Text type="secondary">{formatValue(v)}</Text>
        ),
    },
    {
        title: t("versionDiff.newValue"),
        dataIndex: "new",
        render: (v: unknown) => <Text>{formatValue(v)}</Text>,
    },
];

function formatValue(v: unknown): string {
    if (v === null || v === undefined || v === "") {
        return "—";
    }
    if (typeof v === "boolean") {
        return v ? "true" : "false";
    }
    return String(v);
}

const ParamDiffTable: React.FC<{
    block: { added: ParamDiffEntry[]; removed: ParamDiffEntry[]; modified: ParamDiffEntry[] };
    t: (key: string) => string;
}> = ({ block, t }) => {
    const hasAny =
        block.added.length > 0 ||
        block.removed.length > 0 ||
        block.modified.length > 0;
    if (!hasAny) {
        return <Text type="secondary">{t("versionDiff.noParamChanges")}</Text>;
    }
    return (
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
            {block.added.length > 0 && (
                <div>
                    <Tag color="green" style={{ marginBottom: 8 }}>
                        {t("versionDiff.added")} ({block.added.length})
                    </Tag>
                    {block.added.map((item) => (
                        <div key={`add-${item.path}`} style={{ marginBottom: 4 }}>
                            <Text code>{item.path}</Text>
                        </div>
                    ))}
                </div>
            )}
            {block.removed.length > 0 && (
                <div>
                    <Tag color="red" style={{ marginBottom: 8 }}>
                        {t("versionDiff.removed")} ({block.removed.length})
                    </Tag>
                    {block.removed.map((item) => (
                        <div key={`rm-${item.path}`} style={{ marginBottom: 4 }}>
                            <Text code>{item.path}</Text>
                        </div>
                    ))}
                </div>
            )}
            {block.modified.map((item) => (
                <div key={`mod-${item.path}`}>
                    <Tag color="orange" style={{ marginBottom: 8 }}>
                        {t("versionDiff.modified")}: <Text code>{item.path}</Text>
                    </Tag>
                    <Table
                        size="small"
                        pagination={false}
                        columns={fieldChangeColumns(t)}
                        data={(item.field_changes || []) as FieldChange[]}
                        rowKey="field"
                    />
                </div>
            ))}
        </Space>
    );
};

const ApiModifiedPanel: React.FC<{
    api: ModifiedApiDiff;
    t: (key: string) => string;
}> = ({ api, t }) => (
    <Collapse bordered={false} style={{ marginTop: 8 }}>
        {api.field_changes.length > 0 && (
            <CollapseItem header={t("versionDiff.apiFields")} name="fields">
                <Table
                    size="small"
                    pagination={false}
                    columns={fieldChangeColumns(t)}
                    data={api.field_changes}
                    rowKey="field"
                />
            </CollapseItem>
        )}
        <CollapseItem header={t("versionDiff.requestParams")} name="request">
            <ParamDiffTable block={api.request_params} t={t} />
        </CollapseItem>
        <CollapseItem header={t("versionDiff.responseParams")} name="response">
            <ParamDiffTable block={api.response_params} t={t} />
        </CollapseItem>
    </Collapse>
);

const VersionDiffModal: React.FC<VersionDiffModalProps> = ({
    visible,
    serviceUuid,
    versions,
    currentVersion,
    onClose,
    serviceIterationId,
}) => {
    const { t } = useTranslation();
    const iterationPreviewMode =
        serviceIterationId !== undefined && serviceIterationId > 0;

    const versionOptions = useMemo(
        () => versions.filter((v) => v.version).map((v) => v.version),
        [versions],
    );

    const defaultBase = useMemo(() => {
        const idx = versionOptions.indexOf(currentVersion);
        if (idx >= 0 && idx < versionOptions.length - 1) {
            return versionOptions[idx + 1];
        }
        return versionOptions[1] || versionOptions[0] || "";
    }, [versionOptions, currentVersion]);

    const [baseVersion, setBaseVersion] = useState(defaultBase);
    const [compareVersion, setCompareVersion] = useState(currentVersion);
    const [loading, setLoading] = useState(false);
    const [diff, setDiff] = useState<CompareVersionsByUuidResponse | null>(null);

    useEffect(() => {
        if (visible) {
            setBaseVersion(defaultBase);
            setCompareVersion(currentVersion);
            setDiff(null);
        }
    }, [visible, defaultBase, currentVersion]);

    const fetchDiff = useCallback(async () => {
        setLoading(true);
        try {
            if (iterationPreviewMode && serviceIterationId) {
                const res = await GetIterationChangePreview(serviceIterationId);
                if (res.status !== 200) {
                    throw new Error(res.message);
                }
                setDiff(res);
                return;
            }
            if (!baseVersion || !compareVersion || baseVersion === compareVersion) {
                return;
            }
            const res = await CompareVersionsByUuid(
                serviceUuid,
                baseVersion,
                compareVersion,
            );
            if (res.status !== 200) {
                throw new Error(res.message);
            }
            setDiff(res);
        } catch (err: unknown) {
            setDiff(null);
            Message.warning(toastFromError(err, "toast.compareVersionsFailed"));
        } finally {
            setLoading(false);
        }
    }, [
        serviceUuid,
        baseVersion,
        compareVersion,
        iterationPreviewMode,
        serviceIterationId,
    ]);

    useEffect(() => {
        if (!visible) return;
        if (iterationPreviewMode && serviceIterationId) {
            fetchDiff();
            return;
        }
        if (baseVersion && compareVersion && baseVersion !== compareVersion) {
            fetchDiff();
        }
    }, [
        visible,
        baseVersion,
        compareVersion,
        fetchDiff,
        iterationPreviewMode,
        serviceIterationId,
    ]);

    const hasChanges = useMemo(() => {
        if (!diff?.summary) return false;
        const s = diff.summary;
        return (
            s.service_changed ||
            s.categories_added > 0 ||
            s.categories_removed > 0 ||
            s.categories_modified > 0 ||
            s.apis_added > 0 ||
            s.apis_removed > 0 ||
            s.apis_modified > 0
        );
    }, [diff]);

    return (
        <Modal
            title={
                iterationPreviewMode
                    ? t("approval.changePreviewTitle")
                    : t("versionDiff.title")
            }
            visible={visible}
            onCancel={onClose}
            footer={null}
            style={{ width: 920, maxWidth: "95vw" }}
            unmountOnExit
        >
            {!iterationPreviewMode && (
                <Space wrap style={{ marginBottom: 16 }}>
                    <span>
                        <Text type="secondary">
                            {t("versionDiff.baseVersion")}:{" "}
                        </Text>
                        <Select
                            style={{ width: 140 }}
                            value={baseVersion}
                            onChange={setBaseVersion}
                            options={versionOptions.map((v) => ({
                                label: v,
                                value: v,
                            }))}
                        />
                    </span>
                    <span>
                        <Text type="secondary">
                            {t("versionDiff.compareVersion")}:{" "}
                        </Text>
                        <Select
                            style={{ width: 140 }}
                            value={compareVersion}
                            onChange={setCompareVersion}
                            options={versionOptions.map((v) => ({
                                label: v,
                                value: v,
                            }))}
                        />
                    </span>
                    <Button type="primary" loading={loading} onClick={fetchDiff}>
                        {t("versionDiff.refresh")}
                    </Button>
                </Space>
            )}

            {!iterationPreviewMode && baseVersion === compareVersion && (
                <Empty description={t("versionDiff.sameVersionHint")} />
            )}

            {loading && (
                <div style={{ textAlign: "center", padding: 40 }}>
                    <Spin />
                </div>
            )}

            {!loading &&
                diff &&
                (iterationPreviewMode || baseVersion !== compareVersion) && (
                <>
                    <Space wrap style={{ marginBottom: 16 }}>
                        <Tag>
                            {diff.base_version} → {diff.compare_version}
                        </Tag>
                        {hasChanges ? (
                            <Tag color="orange">{t("versionDiff.hasChanges")}</Tag>
                        ) : (
                            <Tag color="green">{t("versionDiff.noChanges")}</Tag>
                        )}
                        <Text type="secondary">
                            +{diff.summary.apis_added} / -{diff.summary.apis_removed} / ~
                            {diff.summary.apis_modified} API
                        </Text>
                    </Space>

                    {!hasChanges ? (
                        <Empty description={t("versionDiff.noChanges")} />
                    ) : (
                        <Collapse defaultActiveKey={["service", "apis"]}>
                            {diff.summary.service_changed && (
                                <CollapseItem
                                    header={t("versionDiff.serviceSection")}
                                    name="service"
                                >
                                    <Paragraph>
                                        <Text delete type="secondary">
                                            {diff.service_diff.base_description || "—"}
                                        </Text>
                                    </Paragraph>
                                    <Paragraph>
                                        <Text>{diff.service_diff.compare_description || "—"}</Text>
                                    </Paragraph>
                                </CollapseItem>
                            )}

                            {(diff.summary.categories_added > 0 ||
                                diff.summary.categories_removed > 0 ||
                                diff.summary.categories_modified > 0) && (
                                <CollapseItem
                                    header={t("versionDiff.categoriesSection")}
                                    name="categories"
                                >
                                    {diff.categories_diff.added.map((c) => (
                                        <div key={`cadd-${c.id}`}>
                                            <Tag color="green">+</Tag> {c.name}
                                        </div>
                                    ))}
                                    {diff.categories_diff.removed.map((c) => (
                                        <div key={`crm-${c.id}`}>
                                            <Tag color="red">-</Tag> {c.name}
                                        </div>
                                    ))}
                                    {diff.categories_diff.modified.map((c) => (
                                        <div key={`cmod-${c.id}`} style={{ marginTop: 8 }}>
                                            <Tag color="orange">~</Tag> {c.base.name}
                                            <Table
                                                size="small"
                                                pagination={false}
                                                columns={fieldChangeColumns(t)}
                                                data={c.field_changes}
                                                rowKey="field"
                                            />
                                        </div>
                                    ))}
                                </CollapseItem>
                            )}

                            <CollapseItem header={t("versionDiff.apisSection")} name="apis">
                                {diff.apis_diff.added.map((api) => (
                                    <div key={`add-${api.key}`} style={{ marginBottom: 8 }}>
                                        <Tag color="green">{t("versionDiff.added")}</Tag>
                                        {genApiMethodTag(api.method as HttpMethod, "small")}
                                        <Text>{api.name}</Text>
                                        <Text type="secondary"> {api.path}</Text>
                                    </div>
                                ))}
                                {diff.apis_diff.removed.map((api) => (
                                    <div key={`rm-${api.key}`} style={{ marginBottom: 8 }}>
                                        <Tag color="red">{t("versionDiff.removed")}</Tag>
                                        {genApiMethodTag(api.method as HttpMethod, "small")}
                                        <Text>{api.name}</Text>
                                        <Text type="secondary"> {api.path}</Text>
                                    </div>
                                ))}
                                {diff.apis_diff.modified.map((api) => (
                                    <div
                                        key={`mod-${api.key}`}
                                        style={{
                                            marginBottom: 16,
                                            paddingBottom: 12,
                                            borderBottom:
                                                "1px solid var(--color-neutral-3)",
                                        }}
                                    >
                                        <Space>
                                            <Tag color="orange">
                                                {t("versionDiff.modified")}
                                            </Tag>
                                            {genApiMethodTag(api.method as HttpMethod, "small")}
                                            <Text bold>{api.name}</Text>
                                            <Text type="secondary">{api.path}</Text>
                                        </Space>
                                        <ApiModifiedPanel api={api} t={t} />
                                    </div>
                                ))}
                            </CollapseItem>
                        </Collapse>
                    )}
                </>
            )}
        </Modal>
    );
};

export default VersionDiffModal;
