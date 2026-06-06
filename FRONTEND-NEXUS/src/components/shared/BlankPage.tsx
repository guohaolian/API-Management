import React from "react";
import { useTranslation } from "react-i18next";
import { EmptyIconCAM } from "@/assets/icons";
import styles from "./BlankPage.module.less";

const BlankPage: React.FC<{ message?: string; description?: string }> = ({
    message,
    description,
}) => {
    const { t } = useTranslation();

    return (
        <div
            className={styles.loadingCenter}
            style={{ flexDirection: "column" }}
        >
            <img src={EmptyIconCAM} alt="Empty" width={200} />
            <div
                style={{
                    marginTop: 16,
                    color: "var(--color-text-3)",
                    fontSize: 14,
                    textAlign: "center",
                }}
            >
                {message || t("common.noData")}
                {description ? (
                    <div style={{ marginTop: 8, fontSize: 13 }}>{description}</div>
                ) : null}
            </div>
        </div>
    );
};

export default BlankPage;
