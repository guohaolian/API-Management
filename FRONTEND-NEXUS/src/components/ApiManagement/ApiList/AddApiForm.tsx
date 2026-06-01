import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Form, Input, Select } from "@cloud-materials/common";
import type { ApiCategory } from "@/services/service/types";
import { HTTP_METHODS } from "../ApiEdit/types";

interface AddApiFormProps {
    apiCategories?: ApiCategory[];
}

const AddApiForm: React.FC<AddApiFormProps> = ({ apiCategories = [] }) => {
    const { t, i18n } = useTranslation();
    const currentLanguage = i18n.resolvedLanguage;

    const formItemLayout = {
        labelCol: currentLanguage === "en-US" ? { span: 7 } : undefined,
        wrapperCol: currentLanguage === "en-US" ? { span: 17 } : undefined,
    };

    const categories = [
        ...apiCategories,
        { id: -1, name: t("common.uncategorized") },
    ];
    const [name, setName] = useState("");

    return (
        <>
            <Form.Item
                label={t("apiEdit.apiName")}
                field="name"
                rules={[
                    { required: true, message: t("apiEdit.apiNameRequired") },
                    {
                        match: /^[^\u4e00-\u9fff]*$/,
                        message: t("apiEdit.apiNameNoChinese"),
                    },
                ]}
                {...formItemLayout}
            >
                <Input
                    placeholder={t("apiEdit.apiNamePlaceholder")}
                    allowClear
                    onChange={setName}
                />
            </Form.Item>
            <Form.Item
                label={t("api.method")}
                field="method"
                initialValue="GET"
                rules={[{ required: true, message: t("apiEdit.methodRequired") }]}
                {...formItemLayout}
            >
                <Select placeholder={t("apiEdit.methodPlaceholder")}>
                    {HTTP_METHODS.map((m) => (
                        <Select.Option key={m} value={m}>
                            {m}
                        </Select.Option>
                    ))}
                </Select>
            </Form.Item>
            <Form.Item
                label={t("api.path")}
                field="path"
                rules={[
                    { required: true, message: t("apiEdit.pathRequired") },
                    {
                        match: /^\//,
                        message: t("apiEdit.pathMustStartWithSlash"),
                    },
                    {
                        match: /^[^\u4e00-\u9fff]*$/,
                        message: t("apiEdit.apiPathNoChinese"),
                    },
                ]}
                {...formItemLayout}
            >
                <Input placeholder={`/api/${name}`} allowClear />
            </Form.Item>
            <Form.Item
                label={t("apiDetail.apiLevel")}
                field="level"
                initialValue="P2"
                rules={[{ required: true, message: t("apiEdit.levelRequired") }]}
                {...formItemLayout}
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
                label={t("apiEdit.category")}
                field="category_id"
                initialValue={-1}
                rules={[
                    { required: true, message: t("apiEdit.categoryRequired") },
                ]}
                {...formItemLayout}
            >
                <Select placeholder={t("apiEdit.categoryPlaceholder")}>
                    {categories.map((c) => (
                        <Select.Option key={c.id} value={c.id}>
                            {c.name}
                        </Select.Option>
                    ))}
                </Select>
            </Form.Item>
            <Form.Item
                label={t("apiDetail.apiDescription")}
                field="description"
                {...formItemLayout}
            >
                <Input.TextArea
                    placeholder={t("apiEdit.descriptionPlaceholder")}
                    allowClear
                />
            </Form.Item>
        </>
    );
};

export default AddApiForm;
