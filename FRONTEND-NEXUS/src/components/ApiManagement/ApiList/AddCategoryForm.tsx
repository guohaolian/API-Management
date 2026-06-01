import React from "react";
import { useTranslation } from "react-i18next";
import { Form, Input } from "@cloud-materials/common";

const AddCategoryForm: React.FC = () => {
    const { t, i18n } = useTranslation();
    const currentLanguage = i18n.resolvedLanguage;

    return (
        <>
            <Form.Item
                label={t("category.name")}
                labelCol={currentLanguage === "en-US" ? { span: 7 } : undefined}
                wrapperCol={
                    currentLanguage === "en-US" ? { span: 17 } : undefined
                }
                field="category_name"
                rules={[
                    {
                        required: true,
                        message: t("category.nameRequired"),
                    },
                ]}
            >
                <Input placeholder={t("category.namePlaceholder")} allowClear />
            </Form.Item>
            <Form.Item
                label={t("common.description")}
                labelCol={currentLanguage === "en-US" ? { span: 7 } : undefined}
                wrapperCol={
                    currentLanguage === "en-US" ? { span: 17 } : undefined
                }
                field="description"
                rules={[
                    {
                        required: true,
                        message: t("category.descriptionRequired"),
                    },
                ]}
            >
                <Input.TextArea
                    placeholder={t("category.descriptionPlaceholder")}
                    allowClear
                />
            </Form.Item>
        </>
    );
};

export default AddCategoryForm;
