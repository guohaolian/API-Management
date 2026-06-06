import React from "react";
import { Link, Outlet } from "react-router-dom";
import { Layout, PageHeader, Space } from "@cloud-materials/common";
import { useTranslation } from "react-i18next";

import { LogoCAM } from "@/assets/icons";
import ThemeSwitch from "@/components/Theme/ThemeSwitch";
import styles from "./index.module.less";

const DocPortalLayout: React.FC = () => {
    const { t } = useTranslation();

    return (
        <Layout className={styles.portalLayout}>
            <Layout.Header className={styles.portalHeader}>
                <PageHeader
                    title={
                        <Space size={10}>
                            <img src={LogoCAM} alt="NEXUS" width={28} height={28} />
                            <span>{t("docPortal.title")}</span>
                        </Space>
                    }
                    extra={
                        <Space>
                            <ThemeSwitch />
                            <Link to="/" className={styles.manageLink}>
                                {t("docPortal.backToManage")}
                            </Link>
                        </Space>
                    }
                />
            </Layout.Header>
            <Layout.Content className={styles.portalContent}>
                <Outlet />
            </Layout.Content>
        </Layout>
    );
};

export default DocPortalLayout;
