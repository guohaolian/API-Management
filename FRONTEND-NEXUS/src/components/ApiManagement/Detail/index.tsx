import { useTranslation } from "react-i18next";
import { Space, Typography, Divider, Spin } from "@cloud-materials/common";

import styles from "../index.module.less";
import { genApiMethodTag } from "@/utils";
import type { ApiDetail, ApiDraftDetail } from "@/services/api/types";
import BriefInfo from "./BriefInfo";
import RequestParams from "./RequestParams";
import ResponseParams from "./ResponseParams";
import MockConsole from "./MockConsole";
import BlankPage from "@/components/shared/BlankPage";

const { Title } = Typography;

const Detail: React.FC<{
    loading: boolean;
    apiDetail: ApiDetail | ApiDraftDetail;
    isLatest?: boolean;
    serviceUuid?: string;
    currentVersion?: string;
    serviceIterationId?: number;
    showMock?: boolean;
    emptyMessage?: string;
}> = (props) => {
    const { t } = useTranslation();
    const {
        loading,
        apiDetail,
        isLatest = true,
        serviceUuid,
        currentVersion,
        serviceIterationId,
        showMock = true,
        emptyMessage,
    } = props;

    if (loading) {
        return (
            <div className={styles.loadingCenter}>
                <Spin dot />
            </div>
        );
    }

    if (!apiDetail || Object.keys(apiDetail).length === 0) {
        return (
            <BlankPage
                message={
                    emptyMessage || t("apiManagement.noApiStartIteration")
                }
            />
        );
    }

    return (
        <div className={styles.content}>
            <div className={styles.header}>
                <Title heading={5} className={styles.pathTitle}>
                    <Space size={10}>
                        {genApiMethodTag(apiDetail?.method, "medium")}
                        {apiDetail.path}
                    </Space>
                </Title>
            </div>
            <BriefInfo apiDetail={apiDetail} />
            <Divider />
            <RequestParams apiDetail={apiDetail} />
            <Divider />
            <ResponseParams apiDetail={apiDetail} />
            {showMock ? (
                <>
                    <Divider />
                    <MockConsole
                        apiDetail={apiDetail}
                        isLatest={isLatest}
                        serviceUuid={serviceUuid}
                        currentVersion={currentVersion}
                        serviceIterationId={serviceIterationId}
                    />
                </>
            ) : null}
        </div>
    );
};

export default Detail;
