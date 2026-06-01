import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Form, Input } from "@cloud-materials/common";

export const incrementVersion = (version: string): string => {
    if (!version) return "";
    const parts = version.split(".");
    if (parts.length === 3) {
        return `${parts[0]}.${parts[1]}.${Number(parts[2]) + 1}`;
    }
    return "";
};

interface CompleteIterationFormProps {
    currentVersion: string;
    initialNewVersion?: string;
    versionConflict?: boolean;
    conflictServerVersion?: string;
}

const CompleteIterationForm: React.FC<CompleteIterationFormProps> = ({
    currentVersion,
    initialNewVersion,
    versionConflict,
    conflictServerVersion,
}) => {
    const { t, i18n } = useTranslation();
    const currentLanguage = i18n.resolvedLanguage;

    const suggestVersionPlaceholder = useMemo(
        () => initialNewVersion || incrementVersion(currentVersion),
        [currentVersion, initialNewVersion],
    );

    const updatedVersionSuggestion = useMemo(
        () =>
            conflictServerVersion
                ? incrementVersion(conflictServerVersion)
                : "",
        [conflictServerVersion],
    );

    const validateVersion = (
        value: string | undefined,
        callback: (error?: any) => void,
    ) => {
        if (!value) {
            callback();
            return;
        }
        const versionRegex = /^\d+\.\d+\.\d+$/;
        if (!versionRegex.test(value)) {
            callback(t("iteration.versionFormatInvalid"));
            return;
        }

        if (!currentVersion) {
            callback();
            return;
        }

        const [major, minor, patch] = value.split(".").map(Number);
        const [currMajor, currMinor, currPatch] = currentVersion
            .split(".")
            .map(Number);

        if (
            major < currMajor ||
            (major === currMajor && minor < currMinor) ||
            (major === currMajor && minor === currMinor && patch < currPatch)
        ) {
            callback(t("iteration.versionTooLow"));
            return;
        }
        callback();
    };

    return (
        <>
            {versionConflict &&
                conflictServerVersion &&
                updatedVersionSuggestion && (
                    <div
                        style={{
                            color: "#f53f3f",
                            marginBottom: 16,
                            lineHeight: 1.6,
                        }}
                    >
                        {t("iteration.versionConflict", {
                            current: conflictServerVersion,
                            suggested: updatedVersionSuggestion,
                        })}
                    </div>
                )}
            <Form.Item
                label={t("iteration.newVersion")}
                labelCol={
                    currentLanguage === "en-US" ? { span: 7 } : undefined
                }
                wrapperCol={
                    currentLanguage === "en-US" ? { span: 17 } : undefined
                }
                field="new_version"
                initialValue={suggestVersionPlaceholder}
                rules={[
                    {
                        required: true,
                        message: t("iteration.newVersionRequired"),
                    },
                    {
                        validator: validateVersion,
                    },
                ]}
            >
                <Input placeholder={suggestVersionPlaceholder} allowClear />
            </Form.Item>
        </>
    );
};

export default CompleteIterationForm;
