import React from "react";
import { IconMoon, IconSun } from "@arco-design/web-react/icon";
import { useTranslation } from "react-i18next";
import { useTheme } from "@/hooks/useTheme";
import styles from "./themeSwitch.module.less";

const ThemeSwitch: React.FC = () => {
    const { isDark, toggle } = useTheme();
    const { t } = useTranslation();

    return (
        <button
            type="button"
            className={styles.switch}
            aria-label={
                isDark
                    ? t("theme.switchToLight")
                    : t("theme.switchToDark")
            }
            aria-checked={isDark}
            role="switch"
            onClick={(event) => toggle(event)}
        >
            <span className={styles.check}>
                <span className={styles.icon}>
                    <IconSun className={styles.sun} />
                    <IconMoon className={styles.moon} />
                </span>
            </span>
        </button>
    );
};

export default ThemeSwitch;
