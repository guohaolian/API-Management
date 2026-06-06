import { createBrowserRouter, redirect } from "react-router-dom";
import Layout from "@/components/Layout";
import ApiManagement from "@/components/ApiManagement";
import ServiceManagement from "@/components/ServiceManagement";
import PendingApprovals from "@/components/PendingApprovals";
import DocPortal from "@/components/DocPortal";
import DocPortalLayout from "@/components/DocPortal/DocPortalLayout";
import { Message } from "@cloud-materials/common";
import { t } from "i18next";

const requireAuthLoader = () => {
    const token = localStorage.getItem("cam_access_token");
    if (!token) {
        Message.warning(t("common.loginFirst"));
        return redirect("/");
    }
    return null;
};

export const router = createBrowserRouter([
    {
        path: "/portal",
        element: <DocPortalLayout />,
        children: [
            {
                index: true,
                element: <DocPortal />,
            },
        ],
    },
    {
        path: "/",
        element: <Layout />,
        children: [
            {
                index: true,
                element: <ServiceManagement />,
            },
            {
                path: "service",
                element: <ApiManagement />,
                loader: requireAuthLoader,
            },
            {
                path: "approvals",
                element: <PendingApprovals />,
                loader: requireAuthLoader,
            },
        ],
    },
]);

export default router;
