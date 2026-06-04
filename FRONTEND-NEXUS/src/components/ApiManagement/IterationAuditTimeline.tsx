import React, { useCallback, useEffect, useState } from "react";
import {
    Drawer,
    Message,
    Spin,
    Timeline,
    Typography,
} from "@cloud-materials/common";
import { useTranslation } from "react-i18next";
import { GetIterationAuditLog } from "@/services/service";
import type { IterationAuditLogItem } from "@/services/service/types";
import { toastFromError } from "@/i18n/apiMessage";

const { Text } = Typography;

const actionLabelKeys: Record<string, string> = {
    iteration_started: "audit.action.iterationStarted",
    description_updated: "audit.action.descriptionUpdated",
    api_added: "audit.action.apiAdded",
    api_deleted: "audit.action.apiDeleted",
    api_updated: "audit.action.apiUpdated",
    openapi_imported: "audit.action.openapiImported",
    submitted_for_approval: "audit.action.submitted",
    approved: "audit.action.approved",
    rejected: "audit.action.rejected",
    committed: "audit.action.committed",
};

interface IterationAuditTimelineProps {
    serviceIterationId: number;
    visible: boolean;
    onClose: () => void;
}

const IterationAuditTimeline: React.FC<IterationAuditTimelineProps> = ({
    serviceIterationId,
    visible,
    onClose,
}) => {
    const { t } = useTranslation();
    const [loading, setLoading] = useState(false);
    const [logs, setLogs] = useState<IterationAuditLogItem[]>([]);

    const fetchLogs = useCallback(async () => {
        if (serviceIterationId <= 0) return;
        setLoading(true);
        try {
            const res = await GetIterationAuditLog(serviceIterationId);
            if (res.status !== 200) {
                throw new Error(res.message);
            }
            setLogs(res.logs || []);
        } catch (err: unknown) {
            Message.warning(toastFromError(err, "audit.fetchFailed"));
            setLogs([]);
        } finally {
            setLoading(false);
        }
    }, [serviceIterationId]);

    useEffect(() => {
        if (visible) {
            fetchLogs();
        }
    }, [visible, fetchLogs]);

    return (
        <Drawer
            title={t("audit.title")}
            visible={visible}
            onCancel={onClose}
            width={400}
        >
            {loading ? (
                <div style={{ textAlign: "center", padding: 24 }}>
                    <Spin />
                </div>
            ) : logs.length === 0 ? (
                <Text type="secondary">{t("audit.empty")}</Text>
            ) : (
                <Timeline>
                    {logs.map((log) => (
                        <Timeline.Item key={log.id} label={log.created_at || ""}>
                            <Text bold>
                                {t(
                                    actionLabelKeys[log.action] ||
                                        "audit.action.unknown",
                                )}
                            </Text>
                            {log.user && (
                                <div>
                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                        {log.user.nickname || log.user.username}
                                    </Text>
                                </div>
                            )}
                        </Timeline.Item>
                    ))}
                </Timeline>
            )}
        </Drawer>
    );
};

export default IterationAuditTimeline;
