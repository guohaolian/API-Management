import { useCallback, useEffect, useRef, useState } from "react";
import { Message } from "@cloud-materials/common";

import type { ApiDetail, ApiDraftDetail } from "@/services/api/types";
import { GetApiById } from "@/services/api";
import { toastFromError } from "@/i18n/apiMessage";

const useApi = (apiId: number, isLatest: boolean) => {
    const [loading, setLoading] = useState(false);
    const [apiDetail, setApiDetail] = useState<ApiDetail | ApiDraftDetail>(
        {} as ApiDetail,
    );
    const requestSeqRef = useRef(0);

    const fetchApiDetail = useCallback(async () => {
        const requestSeq = ++requestSeqRef.current;
        const requestApiId = apiId;
        const requestIsLatest = isLatest;

        if (!requestApiId || requestApiId <= 0) {
            setApiDetail({} as ApiDetail);
            setLoading(false);
            return;
        }
        setLoading(true);
        try {
            const res = await GetApiById(requestApiId, requestIsLatest);
            if (requestSeq !== requestSeqRef.current) {
                return;
            }
            if (res.status !== 200) {
                setApiDetail({} as ApiDetail);
                throw new Error(res.message || "获取 API 详情失败");
            }
            setApiDetail(res.api || ({} as ApiDetail));
        } catch (error: unknown) {
            if (requestSeq !== requestSeqRef.current) {
                return;
            }
            setApiDetail({} as ApiDetail);
            Message.warning(
                toastFromError(error, "toast.fetchApiDetailFailed"),
            );
        } finally {
            if (requestSeq === requestSeqRef.current) {
                setLoading(false);
            }
        }
    }, [apiId, isLatest]);

    useEffect(() => {
        fetchApiDetail();
    }, [fetchApiDetail]);

    return {
        loading,
        apiDetail,
    };
};

export default useApi;
