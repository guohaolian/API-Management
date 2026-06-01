export const REQUEST_PARAM_TAB_KEYS = [
    "query",
    "path",
    "body",
    "header",
    "cookie",
] as const;

export type RequestParamTabKey = (typeof REQUEST_PARAM_TAB_KEYS)[number];

export const getRequestParamTabTitle = (
    key: RequestParamTabKey,
    t: (translationKey: string) => string,
) => t(`apiDetail.${key}Params`);
