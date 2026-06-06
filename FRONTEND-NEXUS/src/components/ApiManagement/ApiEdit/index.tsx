import React, { useEffect, useRef, useState } from "react";
import {
    Button,
    Space,
    Typography,
    Divider,
    Form,
    Message,
    Spin,
} from "@cloud-materials/common";
import sharedStyles from "../index.module.less";
import BriefInfoEdit from "./BriefInfoEdit";
import {
    transformReqParamsToApiInput,
    transformRespParamsToApiInput,
    serializeApiFormSnapshot,
} from "./utils";
import type {
    ApiDetail,
    ApiDraftDetail,
    ApiReqParamInput,
    ApiRespParamInput,
    UpdateApiByApiDraftIdRequest,
    UpdateApiByApiDraftIdResponse,
} from "@/services/api/types";
import RequestParamsEdit from "./RequestParamsEdit";
import ResponseParamsEdit from "./ResponseParamsEdit";
import MockConsole from "../Detail/MockConsole";
import { confirmAction } from "@/utils";
import BlankPage from "@/components/shared/BlankPage";
import { useTranslation } from "react-i18next";
import { resolveApiMessage, toastFromError } from "@/i18n/apiMessage";
import {
    REQUEST_PARAM_TAB_KEYS,
    type RequestParamTabKey,
} from "../shared/requestParamTabs";

interface ApiEditHandlers {
    handleSaveApiDraft: (
        data: Omit<UpdateApiByApiDraftIdRequest, "service_iteration_id">
    ) => Promise<UpdateApiByApiDraftIdResponse>;
    handleCopyApi: (apiDraftId: number) => Promise<void>;
    handleDeleteApi: (apiDraftId: number) => Promise<void>;
}

interface ApiEditProps {
    loading: boolean;
    /** 仅 API 详情拉取中为 true；勿把迭代列表刷新算入，避免保存后误触发脏状态 */
    detailLoading?: boolean;
    apiDetail: ApiDetail | ApiDraftDetail;
    readOnly?: boolean;
    serviceUuid?: string;
    currentVersion?: string;
    serviceIterationId?: number;
    onDirtyChange?: (dirty: boolean) => void;
    handlers: ApiEditHandlers;
}

const ApiEdit: React.FC<ApiEditProps> = ({
    loading,
    detailLoading,
    apiDetail,
    readOnly = false,
    serviceUuid,
    currentVersion,
    serviceIterationId,
    onDirtyChange,
    handlers: { handleSaveApiDraft, handleCopyApi, handleDeleteApi },
}) => {
    const { t } = useTranslation();
    const [form] = Form.useForm();
    const [editLoading, setEditLoading] = useState(false);
    const [isDraft, setIsDraft] = useState(false);
    const [reqParamsActiveTab, setReqParamsActiveTab] = useState("query");
    const [rejectSubmit, setRejectSubmit] = useState(false); // 是否由于表单填写不全拒绝提交
    const baselineRef = useRef("");
    const isHydratingRef = useRef(false);
    const detailLoadingResolved = detailLoading ?? loading;

    const syncDirtyState = () => {
        if (readOnly) {
            setIsDraft(false);
            return;
        }
        const current = serializeApiFormSnapshot(form.getFieldsValue());
        setIsDraft(current !== baselineRef.current);
    };

    const getFirstTabWithValue = () => {
        if (!apiDetail.request_params_by_location) {
            return "query";
        }
        for (const key of REQUEST_PARAM_TAB_KEYS) {
            if (
                apiDetail.request_params_by_location[key as RequestParamTabKey]
                    ?.length > 0
            ) {
                return key;
            }
        }
        return "query";
    };

    useEffect(() => {
        setIsDraft(false);
    }, [apiDetail.id]);

    useEffect(() => {
        if (detailLoadingResolved || !apiDetail?.id) {
            return;
        }

        isHydratingRef.current = true;
        form.setFieldsValue(apiDetail);
        setReqParamsActiveTab(getFirstTabWithValue());

        const timer = window.setTimeout(() => {
            baselineRef.current = serializeApiFormSnapshot(form.getFieldsValue());
            setIsDraft(false);
            onDirtyChange?.(false);
            isHydratingRef.current = false;
        }, 0);

        return () => {
            window.clearTimeout(timer);
            isHydratingRef.current = false;
        };
    }, [apiDetail.id, detailLoadingResolved, apiDetail, form, onDirtyChange]);

    useEffect(() => {
        onDirtyChange?.(isDraft);
    }, [isDraft, onDirtyChange]);

    // 提交本次apiDraft改动
    const handleSubmit = async () => {
        if (readOnly || rejectSubmit) {
            return;
        }
        const values = await form.validate();
        setEditLoading(true);

        const req_params: ApiReqParamInput[] = transformReqParamsToApiInput(
            values.request_params_by_location
        );
        // 检查是否有请求参数name为空
        if (req_params.some((param) => !param.name)) {
            Message.warning(t("toast.emptyRequestParamName"));
            setEditLoading(false);
            return;
        }
        // 检查是否有Path参数
        const hasPathParams = req_params.some(
            (param) => param.location === "path"
        );
        if (hasPathParams) {
            // 检查apiPath是否包含{param}
            const apiPath = values.path;
            const allPathParams = req_params.filter(
                (param) => param.location === "path"
            );
            // path参数不能为选填
            if (allPathParams.some((param) => param.required === false)) {
                Message.warning(t("toast.pathParamOptional"));
                setEditLoading(false);
                return;
            }
            const allPathParamsShouldInPath = allPathParams.map(
                (param) => `{${param.name}}`
            );

            if (
                !allPathParamsShouldInPath.every((param) =>
                    apiPath.includes(param)
                )
            ) {
                Message.warning(t("toast.pathParamMustBeInPath"));
                setEditLoading(false);
                return;
            }
        }
        const resp_params: ApiRespParamInput[] = transformRespParamsToApiInput(
            values.response_params_by_status_code
        );
        // 检查是否有响应参数name为空
        if (resp_params.some((param) => !param.name)) {
            Message.warning(t("toast.emptyResponseParamName"));
            setEditLoading(false);
            return;
        }

        const data: Omit<UpdateApiByApiDraftIdRequest, "service_iteration_id"> =
            {
                api_draft_id: apiDetail.id,
                name: values.name,
                method: values.method,
                path: values.path,
                description: values.description,
                level: values.level || "P2",
                req_params,
                resp_params,
            };
        try {
            const res = await handleSaveApiDraft(data);
            baselineRef.current = serializeApiFormSnapshot(values);
            setIsDraft(false);
            onDirtyChange?.(false);
            Message.success(
                resolveApiMessage(res.message, "toast.saveApiSuccess"),
            );
        } catch (error) {
            Message.error(toastFromError(error, "toast.saveApiFailed"));
        }
        setEditLoading(false);
    };

    if (!apiDetail || Object.keys(apiDetail).length === 0) {
        return <BlankPage message={t("apiManagement.noApiCreateHint")} />;
    }

    return (
        <div className={sharedStyles.content}>
            <Spin size={40} loading={loading}>
                <div className={sharedStyles.header}>
                    <Typography.Title heading={5}>
                        {t("apiManagement.serviceIteration")}
                    </Typography.Title>
                    <Space>
                        <Button
                            type="default"
                            status="success"
                            onClick={handleSubmit}
                            loading={editLoading}
                            disabled={readOnly || !isDraft || rejectSubmit}
                        >
                            {isDraft
                                ? t("apiManagement.saveApi")
                                : t("apiManagement.apiSaved")}
                        </Button>
                        <Button
                            type="default"
                            status="default"
                            disabled={readOnly}
                            onClick={() => handleCopyApi(apiDetail.id)}
                        >
                            {t("apiManagement.copyApi")}
                        </Button>
                        <Button
                            type="default"
                            status="danger"
                            disabled={readOnly}
                            onClick={() =>
                                confirmAction(
                                    () => handleDeleteApi(apiDetail.id),
                                    "action.delete",
                                    "confirm.deleteApi",
                                    { danger: true },
                                )
                            }
                        >
                            {t("apiManagement.deleteApi")}
                        </Button>
                    </Space>
                </div>
                <Form
                    key={apiDetail.id}
                    form={form}
                    layout="vertical"
                    scrollToFirstError
                    initialValues={apiDetail}
                    disabled={readOnly}
                    onValuesChange={() => {
                        if (readOnly || isHydratingRef.current) {
                            return;
                        }
                        syncDirtyState();
                    }}
                >
                    <BriefInfoEdit />
                    <Divider />
                    <RequestParamsEdit
                        reqParamsActiveTab={reqParamsActiveTab}
                        setReqParamsActiveTab={setReqParamsActiveTab}
                        setRejectSubmit={setRejectSubmit}
                        readOnly={readOnly}
                    />
                    <Divider />
                    <ResponseParamsEdit
                        setRejectSubmit={setRejectSubmit}
                        readOnly={readOnly}
                    />
                </Form>
                <Divider />
                <MockConsole
                    apiDetail={apiDetail}
                    isLatest={false}
                    serviceUuid={serviceUuid}
                    currentVersion={currentVersion}
                    serviceIterationId={serviceIterationId}
                />
            </Spin>
        </div>
    );
};

export default ApiEdit;
