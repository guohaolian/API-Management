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
    ResponseParam,
    ResponseParamDraft,
} from "@/services/api/types";
import { genStatusCodeTag } from "@/utils";
import styles from "../index.module.less";
import { getParamTypeTag } from "./utils";

const { Text } = Typography;

const ResponseParams = (props: { apiDetail: ApiDetail | ApiDraftDetail }) => {
    const { t } = useTranslation();
    const { apiDetail } = props;

    const responseColumns = useMemo(() => {
        const columns = [
            {
                title: t("apiDetail.paramName"),
                dataIndex: "name",
                width: 160,
                render: (
                    v: string,
                    record: ResponseParam | ResponseParamDraft,
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
                                            ResponseParam | ResponseParamDraft
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
                    record: ResponseParam | ResponseParamDraft,
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
                title: t("apiDetail.example"),
                dataIndex: "example",
                placeholder: "-",
            },
        ];
        return columns;
    }, [t]);

    const responseParamsByStatusCode: Record<
        number,
        ResponseParam[] | ResponseParamDraft[]
    > = apiDetail.response_params_by_status_code || {};
    const existCodes: number[] = Object.keys(responseParamsByStatusCode)
        .filter(
            (status) => responseParamsByStatusCode[Number(status)]?.length > 0,
        )
        .map(Number)
        .sort((a, b) => a - b);

    return (
        <Space direction="vertical" size={12}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>
                <IconCommon /> {t("apiDetail.responseParams")}
            </div>
            {existCodes.map((code) => (
                <Space direction="vertical" size={8} key={code}>
                    <Text>
                        {t("apiDetail.statusCode")}
                        {genStatusCodeTag(code)}
                    </Text>
                    <Table<ResponseParam | ResponseParamDraft>
                        pagination={false}
                        columns={responseColumns as any}
                        rowKey="name"
                        data={responseParamsByStatusCode[code]}
                        size="small"
                    />
                </Space>
            ))}
        </Space>
    );
};

export default ResponseParams;
