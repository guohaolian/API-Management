import React, { useEffect, useState } from "react";
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
import { confirmAction } from "@/utils";
import BlankPage from "@/components/BlankPage";
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
    apiDetail: ApiDetail | ApiDraftDetail;
    handlers: ApiEditHandlers;
}

const ApiEdit: React.FC<ApiEditProps> = ({
    loading,
    apiDetail,
    handlers: { handleSaveApiDraft, handleCopyApi, handleDeleteApi },
}) => {
    const { t } = useTranslation();
    const [form] = Form.useForm();
    const [editLoading, setEditLoading] = useState(false);
    const [isDraft, setIsDraft] = useState(false);
    const [reqParamsActiveTab, setReqParamsActiveTab] = useState("query");
    const [rejectSubmit, setRejectSubmit] = useState(false); // 是否由于表单填写不全拒绝提交

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
        form.setFieldsValue(apiDetail);
        setIsDraft(false);
        setReqParamsActiveTab(getFirstTabWithValue());
    }, [apiDetail, form]);

    // 提交本次apiDraft改动
    const handleSubmit = async () => {
        if (rejectSubmit) {
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
            setIsDraft(false);
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
                            disabled={!isDraft || rejectSubmit}
                        >
                            {isDraft
                                ? t("apiManagement.saveApi")
                                : t("apiManagement.apiSaved")}
                        </Button>
                        <Button
                            type="default"
                            status="default"
                            onClick={() => handleCopyApi(apiDetail.id)}
                        >
                            {t("apiManagement.copyApi")}
                        </Button>
                        <Button
                            type="default"
                            status="danger"
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
                    form={form}
                    layout="vertical"
                    scrollToFirstError
                    initialValues={apiDetail}
                    onValuesChange={() => {
                        setIsDraft(true);
                    }}
                >
                    <BriefInfoEdit />
                    <Divider />
                    <RequestParamsEdit
                        reqParamsActiveTab={reqParamsActiveTab}
                        setReqParamsActiveTab={setReqParamsActiveTab}
                        setRejectSubmit={setRejectSubmit}
                    />
                    <Divider />
                    <ResponseParamsEdit setRejectSubmit={setRejectSubmit} />
                </Form>
            </Spin>
        </div>
    );
};

export default ApiEdit;
