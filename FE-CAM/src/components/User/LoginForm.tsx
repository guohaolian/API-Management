import React from "react";
import { useTranslation } from "react-i18next";
import { Form, Input } from "@cloud-materials/common";

const LoginForm: React.FC = () => {
    const { i18n, t } = useTranslation();
    const currentLanguage = i18n.resolvedLanguage;

    const labelCol = currentLanguage === "en-US" ? { span: 7 } : { span: 6 };
    const wrapperCol = currentLanguage === "en-US" ? { span: 17 } : { span: 18 };

    return (
        <>
            <Form.Item
                label={<span style={{ whiteSpace: "nowrap" }}>{t("login.username")}</span>}
                labelCol={labelCol}
                wrapperCol={wrapperCol}
                field="username"
                rules={[
                    {
                        required: true,
                        message: t("login.usernameRequired"),
                    },
                ]}
            >
                <Input
                    placeholder={t("login.usernamePlaceholder")}
                    allowClear
                />
            </Form.Item>
            <Form.Item
                label={<span style={{ whiteSpace: "nowrap" }}>{t("login.password")}</span>}
                labelCol={labelCol}
                wrapperCol={wrapperCol}
                field="password"
                rules={[
                    {
                        required: true,
                        message: t("login.passwordRequired"),
                    },
                ]}
            >
                <Input.Password
                    placeholder={t("login.passwordPlaceholder")}
                    allowClear
                />
            </Form.Item>
        </>
    );
};

export default LoginForm;
