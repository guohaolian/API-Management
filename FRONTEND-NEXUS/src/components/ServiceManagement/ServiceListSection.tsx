import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
    Message,
    CModal,
    Tabs,
    Typography,
    Button,
} from "@cloud-materials/common";

import { useService } from "@/hooks/useService";
import type { ServiceRange } from "@/services/service/types";
import type { UserProfile } from "@/services/user/types";
import ServiceList from "./ServiceList";
import UserSelect from "./UserSelect";
import { toastFromError } from "@/i18n/apiMessage";

const { Title } = Typography;

const ServiceListSection: React.FC<{
    user: UserProfile;
    getUserByUsernameOrNicknameOrEmail: (
        username_or_nickname_or_email: string
    ) => Promise<UserProfile[]>;
}> = ({ user, getUserByUsernameOrNicknameOrEmail }) => {
    const { t } = useTranslation();
    const [serviceRange, setServiceRange] =
        useState<ServiceRange>("MyServices");
    const {
        serviceList,
        loading,
        fetchMyNewestServices,
        fetchMyMaintainedServices,
        fetchMyDeletedServices,
        fetchHisNewestServicesByOwnerId,
        fetchAllServices,
        handleViewService,
        handleDeleteService,
        handleRestoreService,
        handleCreateService,
    } = useService();
    const [pagination, setPagination] = useState({
        page_size: 10,
        current_page: 1,
        total: 0,
    });

    const hisIdRef = useRef<number>(-1);

    const handleTabChange = (key: ServiceRange) => {
        if (key === "HisServices") {
            const modal = CModal.openArcoForm({
                title: t("apiManagement.viewOthersService"),
                content: (
                    <>
                        <UserSelect
                            getUserByUsernameOrNicknameOrEmail={
                                getUserByUsernameOrNicknameOrEmail
                            }
                            onSelectId={(id) => {
                                hisIdRef.current = id;
                            }}
                        />
                    </>
                ),
                cancelText: t("common.cancel"),
                okText: t("common.confirm"),
                onOk: async () => {
                    try {
                        const selectedId = hisIdRef.current;
                        if (selectedId <= 0) {
                            throw new Error(t("toast.noUserSelected"));
                        }
                        setServiceRange("HisServices");
                        setPagination({
                            ...pagination,
                            current_page: 1,
                        });
                        modal.close();
                    } catch (err: unknown) {
                        Message.warning(toastFromError(err, "common.failure"));
                        throw err;
                    }
                },
                onCancel: () => {
                    hisIdRef.current = -1;
                    modal.close();
                    setServiceRange(key);
                    setPagination({
                        ...pagination,
                        current_page: 1,
                    });
                },
            });
        } else {
            setServiceRange(key);
            setPagination({
                ...pagination,
                current_page: 1,
            });
        }
    };

    const handlePageChange = (pageSize: number, currentPage?: number) => {
        setPagination((prev) => ({
            ...prev,
            page_size: pageSize,
            current_page: currentPage || prev.current_page,
        }));
    };

    useEffect(() => {
        switch (serviceRange) {
            case "MyServices":
                fetchMyNewestServices(pagination)
                    .then((total) => {
                        setPagination((prev) => ({
                            ...prev,
                            total,
                        }));
                    })
                    .catch((err) => {
                        Message.warning(
                            toastFromError(err, "toast.fetchServicesFailed"),
                        );
                    });
                break;
            case "MyMaintainedServices":
                fetchMyMaintainedServices(pagination)
                    .then((total) => {
                        setPagination((prev) => ({
                            ...prev,
                            total,
                        }));
                    })
                    .catch((err) => {
                        Message.warning(
                            toastFromError(err, "toast.fetchServicesFailed"),
                        );
                    });
                break;
            case "MyDeletedServices":
                fetchMyDeletedServices(pagination)
                    .then((total) => {
                        setPagination((prev) => ({
                            ...prev,
                            total,
                        }));
                    })
                    .catch((err) => {
                        Message.warning(
                            toastFromError(err, "toast.fetchServicesFailed"),
                        );
                    });
                break;
            case "HisServices":
                fetchHisNewestServicesByOwnerId(hisIdRef.current, pagination)
                    .then((total) => {
                        setPagination((prev) => ({
                            ...prev,
                            total,
                        }));
                    })
                    .catch((err) => {
                        Message.warning(
                            toastFromError(err, "toast.fetchServicesFailed"),
                        );
                    });
                break;
            case "AllServices":
                fetchAllServices(pagination)
                    .then((total) => {
                        setPagination((prev) => ({
                            ...prev,
                            total,
                        }));
                    })
                    .catch((err) => {
                        Message.warning(
                            toastFromError(err, "toast.fetchServicesFailed"),
                        );
                    });
                break;
        }
    }, [serviceRange, pagination.page_size, pagination.current_page]);

    return (
        <>
            <div
                style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: 12,
                }}
            >
                <Title heading={5} style={{ margin: 0 }}>
                    {t("service.list")}
                </Title>
                <Button
                    type="primary"
                    onClick={() => handleCreateService(user)}
                >
                    {t("service.create")}
                </Button>
            </div>

            <Tabs
                activeTab={serviceRange}
                onChange={(key) => handleTabChange(key as ServiceRange)}
                style={{ marginBottom: 18 }}
            >
                <Tabs.TabPane key="MyServices" title={t("service.myServices")} />
                <Tabs.TabPane
                    key="MyMaintainedServices"
                    title={t("service.myMaintainedServices")}
                />
                <Tabs.TabPane
                    key="MyDeletedServices"
                    title={t("service.myDeletedServices")}
                />
                {user.level === 0 && (
                    <Tabs.TabPane
                        key="HisServices"
                        title={t("service.hisServices")}
                    />
                )}
                {user.level === 0 && (
                    <Tabs.TabPane
                        key="AllServices"
                        title={t("service.allServices")}
                    />
                )}
            </Tabs>
            <ServiceList
                serviceList={serviceList}
                range={serviceRange}
                pagination={pagination}
                handlePageChange={handlePageChange}
                handleViewService={handleViewService}
                handleDeleteService={handleDeleteService}
                handleRestoreService={handleRestoreService}
                loading={loading}
                user={user}
            />
        </>
    );
};

export default ServiceListSection;
