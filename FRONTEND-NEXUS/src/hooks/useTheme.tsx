import { useCallback, useEffect, useSyncExternalStore, type MouseEvent } from "react";
import {
    getIsDark,
    getThemePreference,
    initTheme,
    subscribeTheme,
    toggleTheme,
    type ThemeAppearance,
} from "@/theme/appearance";

export function useTheme() {
    const isDark = useSyncExternalStore(
        subscribeTheme,
        getIsDark,
        () => false,
    );
    const preference = useSyncExternalStore(
        subscribeTheme,
        getThemePreference,
        (): ThemeAppearance => "auto",
    );

    useEffect(() => {
        initTheme();
    }, []);

    const toggle = useCallback((event?: MouseEvent<HTMLElement>) => {
        void toggleTheme(
            event
                ? { clientX: event.clientX, clientY: event.clientY }
                : undefined,
        );
    }, []);

    return { isDark, preference, toggle };
}
