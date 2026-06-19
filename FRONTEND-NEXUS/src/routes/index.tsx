import { createBrowserRouter, redirect } from "react-router-dom";
import Layout from "@/components/Layout";
import ApiManagement from "@/components/ApiManagement";
import ServiceManagement from "@/components/ServiceManagement";
import PendingApprovals from "@/components/PendingApprovals";
import DocPortal from "@/components/DocPortal";
import DocPortalLayout from "@/components/DocPortal/DocPortalLayout";
import AuthPage from "@/pages/Auth";

// 未登录时静默跳转到 /login（整个主应用父路由共用）
const requireAuthLoader = () => {
    const token = localStorage.getItem("cam_access_token");
    if (!token) {
        return redirect("/login");
    }
    return null;
};

export const router = createBrowserRouter([
    {
        path: "/login",
        element: <AuthPage />,
    },
    {
        path: "/register",
        element: <AuthPage />,
    },
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
        // 整个主应用都要求登录，loader 在父级统一拦截
        path: "/",
        element: <Layout />,
        loader: requireAuthLoader,
        children: [
            {
                index: true,
                element: <ServiceManagement />,
            },
            {
                path: "service",
                element: <ApiManagement />,
            },
            {
                path: "approvals",
                element: <PendingApprovals />,
            },
        ],
    },
]);

export default router;
