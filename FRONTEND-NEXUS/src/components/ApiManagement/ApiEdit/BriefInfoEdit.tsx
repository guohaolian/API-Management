import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import {
    Input,
    Select,
    Form,
    Space,
    IconCommon,
} from "@cloud-materials/common";
import { HTTP_METHODS } from "./types";

const { TextArea } = Input;

const BriefInfoEdit: React.FC = () => {
    const { t } = useTranslation();
    const { form } = Form.useFormContext();
    const [name, setName] = useState(form.getFieldValue("name"));

    return (
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <div style={{ fontSize: 13, fontWeight: 500 }}>
                <IconCommon /> {t("apiDetail.apiInfo")}
            </div>
            <div style={{ width: "100%" }}>
                <Form.Item
                    label={t("apiEdit.apiName")}
                    field="name"
                    rules={[
                        {
                            required: true,
                            message: t("apiEdit.apiNameRequired"),
                        },
                        {
                            match: /^[^\u4e00-\u9fff]*$/,
                            message: t("apiEdit.apiNameNoChinese"),
                        },
                    ]}
                    style={{ width: "50%" }}
                >
                    <Input
                        placeholder={t("apiEdit.apiNamePlaceholder")}
                        maxLength={50}
                        showWordLimit
                        onChange={(value: string) => {
                            setName(value);
                        }}
                    />
                </Form.Item>
                <Form.Item
                    label={t("apiEdit.methodAndPath")}
                    required
                    style={{ width: "50%" }}
                >
                    <Space direction="horizontal" style={{ width: "100%" }}>
                        <Form.Item
                            field="method"
                            rules={[
                                {
                                    required: true,
                                    message: t("apiEdit.methodRequired"),
                                },
                            ]}
                            noStyle={{ showErrorTip: true }}
                        >
                            <Select
                                style={{ width: 120 }}
                                placeholder={t("apiEdit.methodPlaceholder")}
                            >
                                {HTTP_METHODS.map((method) => (
                                    <Select.Option key={method} value={method}>
                                        {method}
                                    </Select.Option>
                                ))}
                            </Select>
                        </Form.Item>
                        <Form.Item
                            field="path"
                            rules={[
                                {
                                    required: true,
                                    message: t("apiEdit.pathRequired"),
                                },
                                {
                                    match: /^\//,
                                    message: t("apiEdit.pathMustStartWithSlash"),
                                },
                                {
                                    match: /^[^\u4e00-\u9fff]*$/,
                                    message: t("apiEdit.pathNoChinese"),
                                },
                            ]}
                            noStyle={{ showErrorTip: true }}
                        >
                            <Input
                                placeholder={`/api/${name}`}
                                style={{ flex: 1 }}
                            />
                        </Form.Item>
                    </Space>
                </Form.Item>
                <Form.Item
                    label={t("apiDetail.apiLevel")}
                    field="level"
                    rules={[
                        {
                            required: true,
                            message: t("apiEdit.levelRequired"),
                        },
                    ]}
                    style={{ width: "50%" }}
                >
                    <Select placeholder={t("apiEdit.levelPlaceholder")}>
                        {["P0", "P1", "P2", "P3", "P4"].map((l) => (
                            <Select.Option key={l} value={l}>
                                {l}
                            </Select.Option>
                        ))}
                    </Select>
                </Form.Item>
                <Form.Item
                    label={t("apiDetail.apiDescription")}
                    field="description"
                    style={{ width: "50%" }}
                >
                    <TextArea
                        placeholder={t("apiEdit.descriptionPlaceholder")}
                        maxLength={200}
                        showWordLimit
                        autoSize={{ minRows: 3, maxRows: 5 }}
                    />
                </Form.Item>
            </div>
        </Space>
    );
};

export default BriefInfoEdit;
