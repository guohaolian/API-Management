import { Command } from "commander";
import Table from "cli-table3";
import { isValidFilename, isValidVersion, loginRequired } from "../utils/utils";
import { storeServiceInfo, removeService } from "../services/code-generate";
import {
    GetMyMaintainedServices,
    GetMyNewestServices,
} from "../services/apis/service";
import type { ServiceItem } from "../services/apis/service/types";

const PAGE_SIZE = 100;

const fetchAllPages = async (
    fetchPage: (
        page: number
    ) => Promise<{ status: number; message: string; services: ServiceItem[]; total: number }>
): Promise<ServiceItem[]> => {
    const all: ServiceItem[] = [];
    let currentPage = 1;

    while (true) {
        const res = await fetchPage(currentPage);
        if (res.status !== 200) {
            console.error(res.message || "Failed to fetch services");
            process.exit(1);
        }
        all.push(...res.services);
        if (all.length >= res.total) {
            break;
        }
        currentPage += 1;
    }

    return all;
};

const listServices = async () => {
    const [ownedServices, maintainedServices] = await Promise.all([
        fetchAllPages((page) =>
            GetMyNewestServices(PAGE_SIZE, page)
        ),
        fetchAllPages((page) =>
            GetMyMaintainedServices(PAGE_SIZE, page)
        ),
    ]);

    const serviceMap = new Map<
        string,
        { service: ServiceItem; roles: Set<"Owner" | "Maintainer"> }
    >();

    for (const service of ownedServices) {
        serviceMap.set(service.service_uuid, {
            service,
            roles: new Set(["Owner"]),
        });
    }

    for (const service of maintainedServices) {
        const existing = serviceMap.get(service.service_uuid);
        if (existing) {
            existing.roles.add("Maintainer");
        } else {
            serviceMap.set(service.service_uuid, {
                service,
                roles: new Set(["Maintainer"]),
            });
        }
    }

    if (serviceMap.size === 0) {
        console.log("No services available to add.");
        return;
    }

    const table = new Table({
        head: ["Role", "Service UUID", "Version", "Description"],
        wordWrap: true,
        colWidths: [14, 38, 10, 30],
    });

    const rows = [...serviceMap.values()].sort((a, b) =>
        a.service.service_uuid.localeCompare(b.service.service_uuid)
    );

    for (const { service, roles } of rows) {
        table.push([
            [...roles].join(", "),
            service.service_uuid,
            service.version,
            service.description || "-",
        ]);
    }

    console.log(table.toString());
    console.log(
        "\nUsage: nexus add <service_name>:<service_uuid>@<version | latest>"
    );
};

const addService = async (serviceIdentifier: string) => {
    const parts = serviceIdentifier.split("@");
    const nameAndUuid = parts[0];
    const version = parts[1] || "latest";

    if (!isValidVersion(version)) {
        console.error(
            "Invalid version format. Version must be in the format x.y.z (where x, y, and z are non-negative integers)."
        );
        process.exit(1);
    }
    if (!nameAndUuid) {
        console.error(
            "Invalid format. Usage: nexus add <service_name>:<service_uuid>@<version | latest>"
        );
        process.exit(1);
    }

    const [serviceName, serviceUuid] = nameAndUuid.split(":");
    if (!serviceName || !serviceUuid) {
        console.error(
            "Invalid format. Usage: nexus add <service_name>:<service_uuid>@<version | latest>"
        );
        process.exit(1);
    }
    if (!isValidFilename(serviceName)) {
        console.error(
            `Invalid service name: "${serviceName}". Service name must be a valid directory/file name.`
        );
        process.exit(1);
    }

    console.log(`Service Name: ${serviceName}`);
    console.log(`Service UUID: ${serviceUuid}`);
    console.log(`Version: ${version}`);

    await storeServiceInfo(serviceName, serviceUuid, version);
};

export const registerAddServiceCommand = (program: Command) => {
    program
        .command("add <name:uuid@version>")
        .description(
            "Add a service you own or maintain. Usage: nexus add <service_name>:<service_uuid>@<version | latest>"
        )
        .action(loginRequired(addService));
};

export const registerListServiceCommand = (program: Command) => {
    program
        .command("list")
        .description(
            "List services you can add (owned and maintained). Use 'nexus add' to register one."
        )
        .action(loginRequired(listServices));
};

export const registerRemoveServiceCommand = (program: Command) => {
    program
        .command("remove <service_name>")
    .description("Remove a service. Usage: nexus remove <service_name>")
        .action(loginRequired(removeService));
};
