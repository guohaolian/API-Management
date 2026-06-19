import React, { useRef, useState, useEffect, useCallback } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { IconMoon, IconSun, IconLanguage } from "@arco-design/web-react/icon";
import { Message, Select } from "@cloud-materials/common";
import { genUserRoleTag } from "@/utils";
import { useUser } from "@/hooks/useUser";
import { useTheme } from "@/hooks/useTheme";
import { resolveApiMessage, toastFromError } from "@/i18n/apiMessage";
import { LogoCAM } from "@/assets/icons";
import styles from "./index.module.less";
import cx from "./cx";

// ── 滑动动画时长（与 CSS transition 保持一致）──
const DURATION = 720;

type RoleValue =
    | "frontend"
    | "backend"
    | "fullstack"
    | "qa"
    | "devops"
    | "product_manager"
    | "designer"
    | "architect"
    | "proj_lead"
    | "guest";

const ROLES: RoleValue[] = [
    "frontend",
    "backend",
    "fullstack",
    "qa",
    "devops",
    "product_manager",
    "designer",
    "architect",
    "proj_lead",
    "guest",
];

// ─────────────────────────────────────────────────────────────
//  AuthPage
// ─────────────────────────────────────────────────────────────
const AuthPage: React.FC = () => {
    const { t, i18n } = useTranslation();
    const navigate = useNavigate();
    const location = useLocation();
    const { login, register, user } = useUser();
    const { isDark, toggle } = useTheme();

    // 初始模式由路径决定
    const initIsRegister = location.pathname === "/register";

    // signupMode：立即切换（驱动 CSS 滑动动画）
    const [signupMode, setSignupMode] = useState(initIsRegister);
    // showReg：动画进行到一半时切换（切换显示内容）
    const [showReg, setShowReg] = useState(initIsRegister);
    const busyRef = useRef(false);
    const timerRef = useRef<ReturnType<typeof setTimeout>>();
    const timer2Ref = useRef<ReturnType<typeof setTimeout>>();

    // 登录表单状态
    const [loginUsername, setLoginUsername] = useState("");
    const [loginPassword, setLoginPassword] = useState("");
    const [loginLoading, setLoginLoading] = useState(false);

    // 注册表单状态
    const [regUsername, setRegUsername] = useState("");
    const [regNickname, setRegNickname] = useState("");
    const [regEmail, setRegEmail] = useState("");
    const [regRole, setRegRole] = useState<RoleValue | "">("");
    const [regPassword, setRegPassword] = useState("");
    const [regConfirm, setRegConfirm] = useState("");
    const [regLoading, setRegLoading] = useState(false);

    // 已登录则跳首页
    useEffect(() => {
        if (user) navigate("/", { replace: true });
    }, [user, navigate]);

    // 路径变化时同步面板状态（处理浏览器前进/后退）
    useEffect(() => {
        const shouldBeRegister = location.pathname === "/register";
        if (shouldBeRegister !== signupMode) {
            go(shouldBeRegister);
        }
        // 仅在 pathname 变化时触发，避免无限循环
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [location.pathname]);

    // ── 面板滑动切换 ──
    const go = useCallback((toSignup: boolean) => {
        if (busyRef.current) return;
        busyRef.current = true;
        clearTimeout(timerRef.current);
        clearTimeout(timer2Ref.current);

        setSignupMode(toSignup);

        timerRef.current = setTimeout(() => {
            setShowReg(toSignup);
        }, DURATION / 2);

        timer2Ref.current = setTimeout(() => {
            busyRef.current = false;
        }, DURATION);
    }, []);

    const goLogin = () => {
        navigate("/login", { replace: true });
        go(false);
    };

    const goRegister = () => {
        navigate("/register", { replace: true });
        go(true);
    };

    // ── 语言切换 ──
    const toggleLang = () => {
        i18n.changeLanguage(
            i18n.resolvedLanguage === "zh-CN" ? "en-US" : "zh-CN"
        );
    };

    // ── 登录提交 ──
    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!loginUsername.trim()) {
            Message.warning(t("login.usernameRequired"));
            return;
        }
        if (!loginPassword) {
            Message.warning(t("login.passwordRequired"));
            return;
        }
        setLoginLoading(true);
        try {
            const res = await login({
                username: loginUsername.trim(),
                password: loginPassword,
            });
            Message.success(resolveApiMessage(res.message, "login.success"));
            navigate("/");
        } catch (err: unknown) {
            Message.error(toastFromError(err, "login.failure"));
        } finally {
            setLoginLoading(false);
        }
    };

    // ── 注册提交 ──
    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!regUsername.trim()) { Message.warning(t("register.usernameRequired")); return; }
        if (!regNickname.trim()) { Message.warning(t("register.nicknameRequired")); return; }
        if (!regEmail.trim()) { Message.warning(t("register.emailRequired")); return; }
        if (!regRole) { Message.warning(t("register.roleRequired")); return; }
        if (!regPassword) { Message.warning(t("register.passwordRequired")); return; }
        if (!regConfirm) { Message.warning(t("register.confirmPasswordRequired")); return; }

        setRegLoading(true);
        try {
            const regRes = await register({
                username: regUsername.trim(),
                nickname: regNickname.trim(),
                email: regEmail.trim(),
                role: regRole as RoleValue,
                password: regPassword,
                confirmPassword: regConfirm,
            });
            try {
                await login({ username: regUsername.trim(), password: regPassword });
                Message.success(t("register.autoLoginSuccess"));
                navigate("/");
            } catch {
                Message.success(
                    resolveApiMessage(regRes.message, "register.success")
                );
                Message.warning(t("register.autoLoginFailure"));
                goLogin();
            }
        } catch (err: unknown) {
            Message.error(toastFromError(err, "register.failure"));
        } finally {
            setRegLoading(false);
        }
    };

    const isLoading = loginLoading || regLoading;

    return (
        <div className={styles.page}>
            {/* ── 工具栏 ── */}
            <div className={styles.toolbar}>
                <button
                    className={styles.toolBtn}
                    onClick={(e) => toggle(e)}
                    aria-label={
                        isDark ? t("theme.switchToLight") : t("theme.switchToDark")
                    }
                >
                    {isDark ? <IconSun /> : <IconMoon />}
                </button>
                <button
                    className={styles.toolBtn}
                    onClick={toggleLang}
                    aria-label="Switch language"
                >
                    <IconLanguage />
                    <span>{i18n.resolvedLanguage === "zh-CN" ? "EN" : "中"}</span>
                </button>
            </div>

            {/* ── 拟态主卡片 ── */}
            <div
                className={cx(styles.authBox, signupMode && styles.signupMode)}
            >
                {/* 移动端 Tab */}
                <div className={styles.mobileNav}>
                    <div
                        className={cx(styles.mTab, styles.mTabSi)}
                        onClick={goLogin}
                    >
                        {t("login.login").toUpperCase()}
                    </div>
                    <div
                        className={cx(styles.mTab, styles.mTabSu)}
                        onClick={goRegister}
                    >
                        {t("register.submit").toUpperCase()}
                    </div>
                </div>

                {/* ★ 面板 A：表单面板 ★ */}
                <div
                    className={cx(
                        styles.panel,
                        styles.pA,
                        showReg && styles.showReg
                    )}
                >
                    {/* ── 登录表单 ── */}
                    <form
                        className={cx(styles.pInner, styles.pALogin)}
                        onSubmit={handleLogin}
                        autoComplete="off"
                    >
                        <div className={styles.logoRow}>
                            <img
                                src={LogoCAM}
                                alt="logo"
                                className={styles.logoImg}
                            />
                            <span className={styles.logoText}>API NEXUS</span>
                        </div>
                        <div className={styles.fpTitle}>
                            {t("login.pageTitle")}
                        </div>
                        <div className={styles.field}>
                            <input
                                type="text"
                                placeholder={t("login.usernamePlaceholder")}
                                value={loginUsername}
                                onChange={(e) =>
                                    setLoginUsername(e.target.value)
                                }
                                autoComplete="username"
                                disabled={isLoading}
                            />
                        </div>
                        <div className={styles.field}>
                            <input
                                type="password"
                                placeholder={t("login.passwordPlaceholder")}
                                value={loginPassword}
                                onChange={(e) =>
                                    setLoginPassword(e.target.value)
                                }
                                autoComplete="current-password"
                                disabled={isLoading}
                            />
                        </div>
                        <button
                            type="submit"
                            className={cx(styles.btnBlue, styles.btnFull)}
                            disabled={isLoading}
                        >
                            {loginLoading
                                ? t("common.loading")
                                : t("login.login").toUpperCase()}
                        </button>
                    </form>

                    {/* ── 注册表单 ── */}
                    <form
                        className={cx(styles.pInner, styles.pAReg)}
                        onSubmit={handleRegister}
                        autoComplete="off"
                    >
                        <div className={styles.logoRow}>
                            <img
                                src={LogoCAM}
                                alt="logo"
                                className={styles.logoImg}
                            />
                            <span className={styles.logoText}>API NEXUS</span>
                        </div>
                        <div className={styles.fpTitle}>
                            {t("register.pageTitle")}
                        </div>
                        <div className={styles.field}>
                            <input
                                type="text"
                                placeholder={t(
                                    "register.usernamePlaceholder"
                                )}
                                value={regUsername}
                                onChange={(e) => setRegUsername(e.target.value)}
                                autoComplete="username"
                                disabled={isLoading}
                            />
                        </div>
                        <div className={styles.field}>
                            <input
                                type="text"
                                placeholder={t(
                                    "register.nicknamePlaceholder"
                                )}
                                value={regNickname}
                                onChange={(e) => setRegNickname(e.target.value)}
                                autoComplete="nickname"
                                disabled={isLoading}
                            />
                        </div>
                        <div className={styles.field}>
                            <input
                                type="email"
                                placeholder={t("register.emailPlaceholder")}
                                value={regEmail}
                                onChange={(e) => setRegEmail(e.target.value)}
                                autoComplete="email"
                                disabled={isLoading}
                            />
                        </div>
                        <div className={cx(styles.field, styles.roleField)}>
                            <Select
                                value={regRole || undefined}
                                onChange={(v) => setRegRole(v as RoleValue)}
                                placeholder={t("register.rolePlaceholder")}
                                disabled={isLoading}
                                style={{ width: "100%" }}
                            >
                                {ROLES.map((r) => (
                                    <Select.Option key={r} value={r}>
                                        {genUserRoleTag(r)}
                                    </Select.Option>
                                ))}
                            </Select>
                        </div>
                        <div className={styles.field}>
                            <input
                                type="password"
                                placeholder={t(
                                    "register.passwordPlaceholder"
                                )}
                                value={regPassword}
                                onChange={(e) => setRegPassword(e.target.value)}
                                autoComplete="new-password"
                                disabled={isLoading}
                            />
                        </div>
                        <div className={styles.field}>
                            <input
                                type="password"
                                placeholder={t(
                                    "register.confirmPasswordPlaceholder"
                                )}
                                value={regConfirm}
                                onChange={(e) => setRegConfirm(e.target.value)}
                                autoComplete="new-password"
                                disabled={isLoading}
                            />
                        </div>
                        <button
                            type="submit"
                            className={cx(styles.btnBlue, styles.btnFull)}
                            disabled={isLoading}
                        >
                            {regLoading
                                ? t("common.loading")
                                : t("register.submit").toUpperCase()}
                        </button>
                    </form>
                </div>

                {/* ★ 面板 B：拟态覆盖层 ★ */}
                <div
                    className={cx(
                        styles.panel,
                        styles.pB,
                        showReg && styles.showWelcome
                    )}
                >
                    <div className={styles.d1} />
                    <div className={styles.d2} />

                    {/* Hello Friend（登录模式） */}
                    <div className={cx(styles.pInner, styles.pBHello)}>
                        <div className={styles.oTitle}>
                            {t("auth.helloTitle")}
                        </div>
                        <div className={styles.oSub}>{t("auth.helloSub")}</div>
                        <button
                            type="button"
                            className={styles.btnBlue}
                            onClick={goRegister}
                        >
                            {t("register.submit").toUpperCase()}
                        </button>
                    </div>

                    {/* Welcome Back（注册模式） */}
                    <div className={cx(styles.pInner, styles.pBWelcome)}>
                        <div className={styles.oTitle}>
                            {t("auth.welcomeTitle")}
                        </div>
                        <div className={styles.oSub}>
                            {t("auth.welcomeSub")}
                        </div>
                        <button
                            type="button"
                            className={styles.btnBlue}
                            onClick={goLogin}
                        >
                            {t("login.login").toUpperCase()}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AuthPage;
