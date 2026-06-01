import { useTranslation } from "react-i18next";
import { IconCommon, Space, Tabs, Form } from "@cloud-materials/common";
import ParamTable from "./ParamTable";
import {
    REQUEST_PARAM_TAB_KEYS,
    getRequestParamTabTitle,
    type RequestParamTabKey,
} from "../shared/requestParamTabs";

interface RequestParamsEditProps {
    reqParamsActiveTab: string;
    setReqParamsActiveTab: (key: string) => void;
    setRejectSubmit: (reject: boolean) => void;
}

const RequestParamsEdit = ({
    reqParamsActiveTab,
    setReqParamsActiveTab,
    setRejectSubmit,
}: RequestParamsEditProps) => {
    const { t } = useTranslation();

    return (
        <Space direction="vertical" size={12}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>
                <IconCommon /> {t("apiDetail.requestParams")}
            </div>
            <Tabs
                activeTab={reqParamsActiveTab}
                onChange={setReqParamsActiveTab}
            >
                {REQUEST_PARAM_TAB_KEYS.map((key) => (
                    <Tabs.TabPane
                        key={key}
                        title={getRequestParamTabTitle(
                            key as RequestParamTabKey,
                            t,
                        )}
                    />
                ))}
            </Tabs>

            <div>
                {REQUEST_PARAM_TAB_KEYS.map((key) => (
                    <div
                        key={key}
                        style={{
                            display:
                                reqParamsActiveTab === key ? "block" : "none",
                        }}
                    >
                        <Form.Item
                            field={`request_params_by_location.${key}`}
                            triggerPropName="value"
                            noStyle
                        >
                            <ParamTable
                                type="request"
                                setRejectSubmit={setRejectSubmit}
                            />
                        </Form.Item>
                    </div>
                ))}
            </div>
        </Space>
    );
};

export default RequestParamsEdit;
