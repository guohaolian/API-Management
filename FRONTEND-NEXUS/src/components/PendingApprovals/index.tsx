import React, { useCallback, useEffect, useState } from "react";
import {
    Button,
    Input,
    Message,
    Modal,
    Space,
    Table,
    Tag,
    Typography,
} from "@cloud-materials/common";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
    ApproveIteration,
    GetPendingIterations,
    RejectIteration,
} from "@/services/service";
import type { PendingIterationItem } from "@/services/service/types";
import { resolveApiMessage, toastFromError } from "@/i18n/apiMessage";
import VersionDiffModal from "@/components/ApiManagement/modals/VersionDiffModal";
import styles from "./index.module.less";

const { Title, Text } = Typography;

const PendingApprovals: React.FC = () => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [items, setItems] = useState<PendingIterationItem[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const pageSize = 10;
    const [previewId, setPreviewId] = useState<number | null>(null);
    const [rejectId, setRejectId] = useState<number | null>(null);
    const [rejectComment, setRejectComment] = useState("");
    const [actionLoading, setActionLoading] = useState(false);

    const fetchList = useCallback(async () => {
        setLoading(true);
        try {
            const res = await GetPendingIterations(pageSize, page);
            if (res.status !== 200) {
                throw new Error(res.message);
            }
            setItems(res.iterations || []);
            setTotal(res.total || 0);
        } catch (err: unknown) {
            Message.warning(
                toastFromError(err, "approval.fetchPendingFailed"),
            );
            setItems([]);
            setTotal(0);
        } finally {
            setLoading(false);
        }
    }, [page]);

    useEffect(() => {
        fetchList();
    }, [fetchList]);

    const handleApprove = async (row: PendingIterationItem) => {
        setActionLoading(true);
        try {
            const res = await ApproveIteration({
                service_iteration_id: row.service_iteration_id,
            });
            if (res.status !== 200) {
                throw new Error(res.message);
            }
            Message.success(
                resolveApiMessage(res.message, "approval.approveSuccess"),
            );
            await fetchList();
        } catch (err: unknown) {
            Message.warning(toastFromError(err, "approval.approveFailed"));
        } finally {
            setActionLoading(false);
        }
    };

    const handleRejectSubmit = async () => {
        if (!rejectId || !rejectComment.trim()) {
            Message.warning(t("approval.rejectCommentRequired"));
            return;
        }
        setActionLoading(true);
        try {
            const res = await RejectIteration({
                service_iteration_id: rejectId,
                review_comment: rejectComment.trim(),
            });
            if (res.status !== 200) {
                throw new Error(res.message);
            }
            Message.success(
                resolveApiMessage(res.message, "approval.rejectSuccess"),
            );
            setRejectId(null);
            setRejectComment("");
            await fetchList();
        } catch (err: unknown) {
            Message.warning(toastFromError(err, "approval.rejectFailed"));
        } finally {
            setActionLoading(false);
        }
    };

    const columns = [
        {
            title: t("approval.serviceUuid"),
            dataIndex: "service_uuid",
            render: (uuid: string) => (
                <Text copyable>{uuid}</Text>
            ),
        },
        {
            title: t("approval.baseVersion"),
            dataIndex: "base_version",
            width: 100,
        },
        {
            title: t("approval.proposedVersion"),
            dataIndex: "proposed_version",
            width: 120,
            render: (v: string) => <Tag color="arcoblue">{v}</Tag>,
        },
        {
            title: t("approval.submittedBy"),
            dataIndex: "submitted_by",
            render: (u: PendingIterationItem["submitted_by"]) =>
                u ? `${u.nickname || u.username}` : "—",
        },
        {
            title: t("approval.submittedAt"),
            dataIndex: "submitted_at",
            width: 180,
            render: (v: string | null) => v || "—",
        },
        {
            title: t("common.operation"),
            width: 280,
            render: (_: unknown, row: PendingIterationItem) => (
                <Space>
                    <Button
                        size="small"
                        onClick={() =>
                            setPreviewId(row.service_iteration_id)
                        }
                    >
                        {t("approval.viewChanges")}
                    </Button>
                    <Button
                        size="small"
                        type="primary"
                        loading={actionLoading}
                        onClick={() => handleApprove(row)}
                    >
                        {t("approval.approve")}
                    </Button>
                    <Button
                        size="small"
                        status="danger"
                        onClick={() => {
                            setRejectId(row.service_iteration_id);
                            setRejectComment("");
                        }}
                    >
                        {t("approval.reject")}
                    </Button>
                    <Button
                        size="small"
                        type="text"
                        onClick={() =>
                            navigate(
                                `/service?uuid=${encodeURIComponent(row.service_uuid)}`,
                            )
                        }
                    >
                        {t("common.view")}
                    </Button>
                </Space>
            ),
        },
    ];

    return (
        <div className={styles.page}>
            <Title heading={5}>{t("approval.pendingTitle")}</Title>
            <Text type="secondary" style={{ display: "block", marginBottom: 16 }}>
                {t("approval.pendingHint")}
            </Text>
            <Table
                loading={loading}
                columns={columns}
                data={items}
                rowKey="service_iteration_id"
                pagination={{
                    total,
                    current: page,
                    pageSize,
                    onChange: (p) => setPage(p),
                }}
                noDataElement={t("approval.noPending")}
            />
            <VersionDiffModal
                visible={previewId !== null}
                serviceUuid=""
                versions={[]}
                currentVersion=""
                serviceIterationId={previewId ?? undefined}
                onClose={() => setPreviewId(null)}
            />
            <Modal
                title={t("approval.rejectTitle")}
                visible={rejectId !== null}
                onOk={handleRejectSubmit}
                onCancel={() => setRejectId(null)}
                confirmLoading={actionLoading}
            >
                <Input.TextArea
                    placeholder={t("approval.rejectCommentPlaceholder")}
                    value={rejectComment}
                    onChange={setRejectComment}
                    rows={4}
                />
            </Modal>
        </div>
    );
};

export default PendingApprovals;
