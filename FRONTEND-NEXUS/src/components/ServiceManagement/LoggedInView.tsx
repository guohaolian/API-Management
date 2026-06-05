import React from "react";
import { Divider } from "@cloud-materials/common";

import styles from "./index.module.less";
import type { UserProfile } from "@/services/user/types";
import ServiceListSection from "./ServiceListSection";
import { WelcomeLoggedIn } from "./WelcomeView";

const LoggedInView: React.FC<{
    user: UserProfile;
    getUserByUsernameOrNicknameOrEmail: (
        username_or_nickname_or_email: string
    ) => Promise<UserProfile[]>;
}> = ({ user, getUserByUsernameOrNicknameOrEmail }) => {
    return (
        <div className={styles.home}>
            <WelcomeLoggedIn user={user} />
            <Divider />
            <ServiceListSection
                user={user}
                getUserByUsernameOrNicknameOrEmail={
                    getUserByUsernameOrNicknameOrEmail
                }
            />
        </div>
    );
};

export default LoggedInView;
