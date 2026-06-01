import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
    IconCommon,
    Popover,
    Space,
    Table,
    Tag,
    Typography,
} from "@cloud-materials/common";

import type {
    ApiDetail,
    ApiDraftDetail,
    ParamType,
    RequestParam,
    RequestParamDraft,
} from "@/services/api/types";
import styles from "../index.module.less";
import { getParamTypeTag } from "./utils";
import {
    REQUEST_PARAM_TAB_KEYS,
    getRequestParamTabTitle,
    type RequestParamTabKey,
} from "../shared/requestParamTabs";

const { Text } = Typography;

const RequestParams = (props: { apiDetail: ApiDetail | ApiDraftDetail }) => {
    const { t } = useTranslation();
    const { apiDetail } = props;

    const requestColumns = useMemo(() => {
        const columns = [
            {
                title: t("apiDetail.paramName"),
                dataIndex: "name",
                width: 160,
                render: (
                    v: string,
                    record: RequestParam | RequestParamDraft,
                ) => {
                    const childrenParams = record.children_params || [];
                    const showSubParams =
                        record.type === "object" ||
                        (record.type === "array" &&
                            record.array_child_type === "object");

                    if (!showSubParams) {
                        return v;
                    }

                    const popoverText =
                        record.type === "array" &&
                        record.array_child_type === "object"
                            ? t("apiDetail.clickViewArrayChild")
                            : t("apiDetail.clickViewChild");

                    return (
                        <Popover content={popoverText}>
                            <Popover
                                trigger="click"
                                content={
                                    childrenParams.length > 0 ? (
                                        <Table<
                                            RequestParam | RequestParamDraft
                                        >
                                            pagination={false}
                                            columns={columns as any}
                                            rowKey="name"
                                            data={childrenParams}
                                            size="small"
                                        />
                                    ) : (
                                        <div style={{ padding: 12 }}>
                                            <Text type="secondary">
                                                {t("apiDetail.noChildParams")}
                                            </Text>
                                        </div>
                                    )
                                }
                                style={{ width: 1000, maxWidth: 1000 }}
                            >
                                <Text
                                    type="primary"
                                    className={styles.hasChildParamTitle}
                                >
                                    {v}
                                </Text>
                            </Popover>
                        </Popover>
                    );
                },
            },
            {
                title: t("apiDetail.paramType"),
                dataIndex: "type",
                width: 150,
                render: (
                    v: ParamType,
                    record: RequestParam | RequestParamDraft,
                ) => getParamTypeTag(v, record.array_child_type ?? undefined),
            },
            {
                title: t("apiDetail.required"),
                dataIndex: "required",
                width: 120,
                render: (v: boolean) => (
                    <Tag color={v ? "red" : "gray"}>
                        {v
                            ? t("apiDetail.requiredYes")
                            : t("apiDetail.requiredNo")}
                    </Tag>
                ),
            },
            {
                title: t("apiDetail.description"),
                dataIndex: "description",
                width: 240,
                placeholder: "-",
            },
            {
                title: t("apiDetail.defaultValue"),
                dataIndex: "default_value",
                width: 200,
                placeholder: "-",
            },
            {
                title: t("apiDetail.example"),
                dataIndex: "example",
                width: 200,
                placeholder: "-",
            },
        ];
        return columns;
    }, [t]);

    const requestParamsByLocation: Record<
        string,
        RequestParam[] | RequestParamDraft[]
    > = apiDetail.request_params_by_location || {};
    const existLocations = Object.keys(requestParamsByLocation).filter(
        (location) => requestParamsByLocation[location]?.length > 0,
    );

    return (
        <Space direction="vertical" size={12}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>
                <IconCommon /> {t("apiDetail.requestParams")}
            </div>
            {REQUEST_PARAM_TAB_KEYS.filter((key) =>
                existLocations.includes(key),
            ).map((location) => (
                <Space direction="vertical" size={8} key={location}>
                    <Text>
                        {getRequestParamTabTitle(
                            location as RequestParamTabKey,
                            t,
                        )}
                    </Text>
                    <Table<RequestParam | RequestParamDraft>
                        pagination={false}
                        columns={requestColumns as any}
                        rowKey="name"
                        data={requestParamsByLocation[location]}
                        size="small"
                    />
                </Space>
            ))}
        </Space>
    );
};

export default RequestParams;
