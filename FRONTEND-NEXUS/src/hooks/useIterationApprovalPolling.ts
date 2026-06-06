import { useEffect, useRef } from "react";
import { Message } from "@cloud-materials/common";
import { t } from "i18next";
import { GetIterationById } from "@/services/service";
import type { IterationApprovalStatus } from "@/services/service/types";

const POLL_INTERVAL_MS = 10_000;
const STORAGE_KEY_PREFIX = "nexus:pending-approval:";

export type PendingApprovalRecord = {
    iterationId: number;
};

export const pendingApprovalStorageKey = (serviceUuid: string) =>
    `${STORAGE_KEY_PREFIX}${serviceUuid}`;

export const markIterationPendingApproval = (
    serviceUuid: string,
    iterationId: number,
) => {
    sessionStorage.setItem(
        pendingApprovalStorageKey(serviceUuid),
        JSON.stringify({ iterationId } satisfies PendingApprovalRecord),
    );
};

export const clearIterationPendingApproval = (serviceUuid: string) => {
    sessionStorage.removeItem(pendingApprovalStorageKey(serviceUuid));
};

const readPendingApproval = (
    serviceUuid: string,
): PendingApprovalRecord | null => {
    try {
        const raw = sessionStorage.getItem(
            pendingApprovalStorageKey(serviceUuid),
        );
        if (!raw) return null;
        const parsed = JSON.parse(raw) as PendingApprovalRecord;
        return parsed?.iterationId > 0 ? parsed : null;
    } catch {
        return null;
    }
};

type UseIterationApprovalPollingOptions = {
    serviceUuid: string;
    inIteration: boolean;
    iterationId: number;
    iterationApprovalStatus?: IterationApprovalStatus;
    onApproved?: () => void;
    onRejected?: (iterationId: number, reviewComment?: string | null) => void;
};

export const useIterationApprovalPolling = ({
    serviceUuid,
    inIteration,
    iterationId,
    iterationApprovalStatus,
    onApproved,
    onRejected,
}: UseIterationApprovalPollingOptions) => {
    const notifiedRef = useRef(false);
    const onApprovedRef = useRef(onApproved);
    const onRejectedRef = useRef(onRejected);

    onApprovedRef.current = onApproved;
    onRejectedRef.current = onRejected;

    useEffect(() => {
        if (!serviceUuid) return;

        const storedPending = readPendingApproval(serviceUuid);
        const watchingInIteration =
            inIteration &&
            iterationId > 0 &&
            iterationApprovalStatus === "pending";
        const watchedIterationId = watchingInIteration
            ? iterationId
            : storedPending?.iterationId ?? -1;

        if (watchedIterationId <= 0 || notifiedRef.current) {
            return;
        }

        const notifyApproved = () => {
            if (notifiedRef.current) return;
            notifiedRef.current = true;
            clearIterationPendingApproval(serviceUuid);
            Message.success(t("approval.approvedNotify"));
            onApprovedRef.current?.();
        };

        const notifyRejected = (reviewComment?: string | null) => {
            if (notifiedRef.current) return;
            notifiedRef.current = true;
            clearIterationPendingApproval(serviceUuid);
            const base = t("approval.rejectedNotify");
            Message.warning(
                reviewComment ? `${base}: ${reviewComment}` : base,
            );
            onRejectedRef.current?.(watchedIterationId, reviewComment);
        };

        const poll = async () => {
            try {
                const res = await GetIterationById(watchedIterationId);
                if (res.status === -3) {
                    notifyApproved();
                    return;
                }
                if (res.status !== 200) {
                    return;
                }
                const status = res.iteration?.approval_status;
                if (status === "rejected") {
                    notifyRejected(res.iteration?.review_comment);
                }
            } catch {
                /* ignore transient poll errors */
            }
        };

        void poll();
        const timer = window.setInterval(() => {
            void poll();
        }, POLL_INTERVAL_MS);

        return () => {
            window.clearInterval(timer);
        };
    }, [
        serviceUuid,
        inIteration,
        iterationId,
        iterationApprovalStatus,
    ]);
};
