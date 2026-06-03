export type ThemeAppearance = "auto" | "light" | "dark";

export const THEME_STORAGE_KEY = "nexus-theme-appearance";

const mediaQuery =
    typeof window !== "undefined"
        ? window.matchMedia("(prefers-color-scheme: dark)")
        : null;

let userPreference: ThemeAppearance = "auto";
let isDark = false;
const listeners = new Set<() => void>();

function readStoredPreference(): ThemeAppearance {
    if (typeof localStorage === "undefined") {
        return "auto";
    }

    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "auto" || stored === "light" || stored === "dark") {
        return stored;
    }

    return "auto";
}

function resolveIsDark(preference: ThemeAppearance): boolean {
    if (preference === "dark") {
        return true;
    }

    if (preference === "light") {
        return false;
    }

    return mediaQuery?.matches ?? false;
}

export function applyTheme(dark: boolean) {
    if (typeof document === "undefined") {
        return;
    }

    document.documentElement.classList.toggle("dark", dark);

    if (dark) {
        document.body.setAttribute("arco-theme", "dark");
    } else {
        document.body.removeAttribute("arco-theme");
    }
}

function emitChange() {
    listeners.forEach((listener) => listener());
}

function syncTheme(preference: ThemeAppearance) {
    userPreference = preference;
    isDark = resolveIsDark(preference);
    applyTheme(isDark);
    emitChange();
}

export function initTheme() {
    if (typeof window === "undefined") {
        return;
    }

    syncTheme(readStoredPreference());

    mediaQuery?.addEventListener("change", (event) => {
        if (userPreference !== "auto") {
            return;
        }

        isDark = event.matches;
        applyTheme(isDark);
        emitChange();
    });
}

export function getIsDark() {
    return isDark;
}

export function getThemePreference() {
    return userPreference;
}

export function subscribeTheme(listener: () => void) {
    listeners.add(listener);
    return () => listeners.delete(listener);
}

function enableTransitions() {
    return (
        typeof document !== "undefined" &&
        "startViewTransition" in document &&
        window.matchMedia("(prefers-reduced-motion: no-preference)").matches
    );
}

/** VitePress-style toggle: cycles between explicit light/dark and system auto. */
function performThemeToggle() {
    if (!mediaQuery) {
        return isDark;
    }

    const nextIsDark = !isDark;
    applyTheme(nextIsDark);
    isDark = nextIsDark;

    const nextPreference: ThemeAppearance = nextIsDark
        ? mediaQuery.matches
            ? "auto"
            : "dark"
        : mediaQuery.matches
          ? "light"
          : "auto";

    userPreference = nextPreference;
    localStorage.setItem(THEME_STORAGE_KEY, nextPreference);
    emitChange();

    return nextIsDark;
}

export async function toggleTheme(event?: {
    clientX: number;
    clientY: number;
}) {
    if (typeof window === "undefined" || !mediaQuery) {
        return;
    }

    if (!enableTransitions() || !event) {
        performThemeToggle();
        return;
    }

    const { clientX: x, clientY: y } = event;
    const clipPath = [
        `circle(0px at ${x}px ${y}px)`,
        `circle(${Math.hypot(
            Math.max(x, innerWidth - x),
            Math.max(y, innerHeight - y),
        )}px at ${x}px ${y}px)`,
    ];

    const transition = document.startViewTransition(() => {
        performThemeToggle();
    });

    await transition.ready;

    document.documentElement.animate(
        { clipPath: isDark ? [...clipPath].reverse() : clipPath },
        {
            duration: 300,
            easing: "ease-in",
            fill: "forwards",
            pseudoElement: `::view-transition-${isDark ? "old" : "new"}(root)`,
        },
    );
}
