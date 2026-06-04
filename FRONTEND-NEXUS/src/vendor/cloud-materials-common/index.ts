import React, { type CSSProperties, type ReactNode } from "react";
import {
    Alert,
    Avatar,
    Badge,
    Breadcrumb,
    Button,
    Descriptions,
    Divider,
    Drawer,
    Dropdown,
    Form,
    Input,
    Layout,
    Menu,
    Message,
    Modal,
    PageHeader,
    Popconfirm,
    Popover,
    Select,
    Space,
    Spin,
    Switch,
    Table,
    Tabs,
    Tag,
    Timeline,
    Tooltip,
    Tree,
    Typography,
    Watermark,
} from "@arco-design/web-react";
import type { TableColumnProps } from "@arco-design/web-react";

import {
    IconApps,
    IconDown,
    IconDelete,
    IconLanguage,
    IconLoading,
    IconLock,
    IconPoweroff,
    IconPlus,
    IconUser,
    IconUserGroup,
} from "@arco-design/web-react/icon";

export {
    Alert,
    Avatar,
    Badge,
    Breadcrumb,
    Button,
    Descriptions,
    Divider,
    Drawer,
    Dropdown,
    Form,
    Input,
    Layout,
    Menu,
    Message,
    Modal,
    PageHeader,
    Popconfirm,
    Popover,
    Select,
    Space,
    Spin,
    Switch,
    Table,
    Tabs,
    Tag,
    Timeline,
    Tooltip,
    Tree,
    Typography,
    Watermark,

    IconDown,
    IconDelete,
    IconLanguage,
    IconLoading,
    IconLock,
    IconPoweroff,
    IconPlus,
    IconUser,
    IconUserGroup,
};

export type { TableColumnProps };

export const IconCommon: typeof IconApps = IconApps;

type ConfirmOptions = {
    title?: ReactNode;
    content?: ReactNode;
    okText?: string;
    cancelText?: string;
    onOk?: () => void | Promise<void>;
    onCancel?: () => void | Promise<void>;
};

type OpenArcoFormOptions<TValues extends Record<string, any> = Record<string, any>> = {
    title: ReactNode;
    content: ReactNode;
    okText?: string;
    cancelText?: string;
    width?: number;
    modalStyle?: CSSProperties;
    onOk?: (values: TValues, form: any) => void | Promise<void>;
    onCancel?: () => void | Promise<void>;
};

export const CModal = {
    confirm: (options: ConfirmOptions) =>
        Modal.confirm({
            title: options.title,
            content: options.content,
            okText: options.okText,
            cancelText: options.cancelText,
            onOk: options.onOk,
            onCancel: options.onCancel,
        }),
    openArcoForm: <TValues extends Record<string, any> = Record<string, any>>(
        options: OpenArcoFormOptions<TValues>
    ) => {
        const formHolder: { current: any } = { current: null };

        const FormContainer = () => {
            const useForm = (Form as any).useForm as undefined | (() => any);
            const formTuple = useForm ? useForm() : [];
            const form = Array.isArray(formTuple) ? formTuple[0] : formTuple;
            formHolder.current = form;

            return React.createElement(Form as any, { form }, options.content);
        };

        const modalStyle = options.width
            ? { ...(options.modalStyle || {}), width: options.width }
            : options.modalStyle;

        const modal = Modal.confirm({
            title: options.title,
            content: React.createElement(FormContainer),
            style: modalStyle,
            okText: options.okText,
            cancelText: options.cancelText,
            closable: true,
            onOk: async () => {
                const form = formHolder.current;
                const values =
                    form && typeof form.getFieldsValue === "function"
                        ? (form.getFieldsValue() as TValues)
                        : ({} as TValues);
                return options.onOk?.(values, form);
            },
            onCancel: async () => {
                return options.onCancel?.();
            },
        });

        return modal as any;
    },
};
