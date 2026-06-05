import React from "react";
import { useSearchParams } from "react-router-dom";
import { useUser } from "@/hooks/useUser";
import ServiceListSection from "@/components/ServiceManagement/ServiceListSection";
import serviceStyles from "@/components/ServiceManagement/index.module.less";
import ApiManagementDetail from "./ApiManagementDetail";

const ApiManagement: React.FC = () => {
    const [searchParams] = useSearchParams();
    const uuid = searchParams.get("uuid") || "";
    const { user, getUserByUsernameOrNicknameOrEmail } = useUser();

    if (!uuid) {
        if (!user) {
            return null;
        }
        return (
            <div className={serviceStyles.home}>
                <ServiceListSection
                    user={user}
                    getUserByUsernameOrNicknameOrEmail={
                        getUserByUsernameOrNicknameOrEmail
                    }
                />
            </div>
        );
    }

    return <ApiManagementDetail uuid={uuid} />;
};

export default ApiManagement;
