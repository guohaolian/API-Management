import { useCallback, useEffect, useState } from "react";
import { Message } from "@cloud-materials/common";

import type { ApiDetail, ApiDraftDetail } from "@/services/api/types";
import { GetApiById } from "@/services/api";
import { toastFromError } from "@/i18n/apiMessage";

const useApi = (apiId: number, isLatest: boolean) => {
    const [loading, setLoading] = useState(false);
    const [apiDetail, setApiDetail] = useState<ApiDetail | ApiDraftDetail>(
        {} as ApiDetail
    );

    const fetchApiDetail = useCallback(async () => {
        if (!apiId || apiId <= 0) {
            setApiDetail({} as ApiDetail);
            return;
        }
        setLoading(true);
        try {
            const res = await GetApiById(apiId, isLatest);
            if (res.status !== 200) {
                setApiDetail({} as ApiDetail);
                throw new Error(res.message || "获取 API 详情失败");
            }
            setApiDetail(res.api || ({} as ApiDetail));
        } catch (error: unknown) {
            setApiDetail({} as ApiDetail);
            Message.warning(
                toastFromError(error, "toast.fetchApiDetailFailed"),
            );
        } finally {
            setLoading(false);
        }
    }, [apiId]);

    useEffect(() => {
        fetchApiDetail();
    }, [fetchApiDetail]);

    return {
        loading,
        apiDetail,
    };
};

export default useApi;
