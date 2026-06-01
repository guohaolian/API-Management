import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Descriptions, IconCommon, Space } from "@cloud-materials/common";

import type { ApiDetail, ApiDraftDetail, ApiLevel } from "@/services/api/types";
import { genApiLevelTag, formatDateOrDateTime, userAvatar } from "@/utils";
import type { UserProfile } from "@/services/user/types";

const BriefInfo = (props: { apiDetail: ApiDetail | ApiDraftDetail }) => {
    const { t } = useTranslation();
    const { apiDetail } = props;

    const apiBriefInfo = useMemo(
        () => [
            {
                label: t("apiDetail.apiName"),
                value: apiDetail.name,
            },
            {
                label: t("apiDetail.apiOwner"),
                value: userAvatar([apiDetail.owner] as UserProfile[], 25),
            },
            {
                label: t("apiDetail.apiLevel"),
                value: genApiLevelTag(apiDetail.level as ApiLevel, "small"),
            },
            {
                label: t("common.createTime"),
                value: apiDetail.created_at
                    ? formatDateOrDateTime(apiDetail.created_at)
                    : "-",
            },
            {
                label: t("common.updateTime"),
                value: apiDetail.updated_at
                    ? formatDateOrDateTime(apiDetail.updated_at)
                    : "-",
            },
            {
                label: t("apiDetail.apiDescription"),
                value: apiDetail.description || "-",
            },
        ],
        [apiDetail, t],
    );

    return (
        <Space direction="vertical" size={12}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>
                <IconCommon /> {t("apiDetail.apiInfo")}
            </div>
            <Descriptions
                data={apiBriefInfo}
                layout="inline-vertical"
                style={{ marginBottom: -10 }}
            />
        </Space>
    );
};

export default BriefInfo;
