import { t } from "i18next";

/** Maps backend English `message` strings to i18n keys. */
const BACKEND_MESSAGE_KEY_MAP: Record<string, string> = {
    "Get services success": "backend.getServicesSuccess",
    "Service not found": "backend.serviceNotFound",
    "You are not the owner of this service": "backend.notServiceOwner",
    "Get service success": "backend.getServiceSuccess",
    "You are neither the owner nor the maintainer of this service":
        "backend.notOwnerOrMaintainer",
    "Service version not found": "backend.serviceVersionNotFound",
    "You are not the creator of this service iteration":
        "backend.notIterationCreator",
    "Get service versions success": "backend.getServiceVersionsSuccess",
    "Compare service versions success": "backend.compareVersionsSuccess",
    "Base version and compare version must differ":
        "backend.compareVersionsSame",
    "Service UUID already exists": "backend.serviceUuidExists",
    "Create service success": "backend.createServiceSuccess",
    "Get deleted services success": "backend.getDeletedServicesSuccess",
    "Check service maintainer success": "backend.checkMaintainerSuccess",
    "Service owner cannot be added as a maintainer":
        "backend.ownerCannotBeMaintainer",
    "Candidate not found": "backend.candidateNotFound",
    "Remove service maintainer success": "backend.removeMaintainerSuccess",
    "Add service maintainer success": "backend.addMaintainerSuccess",
    "Delete service success": "backend.deleteServiceSuccess",
    "Service is not deleted": "backend.serviceNotDeleted",
    "Restore service success": "backend.restoreServiceSuccess",
    "No service iteration found": "backend.noServiceIterationFound",
    "You are neither the owner of this service, nor the creator of this service iteration":
        "backend.notOwnerOrIterationCreator",
    "Delete service iteration success": "backend.deleteIterationSuccess",
    "Service iteration not found": "backend.serviceIterationNotFound",
    "Service iteration not found or committed":
        "backend.serviceIterationNotFoundOrCommitted",
    "Service iteration has been committed":
        "backend.serviceIterationCommitted",
    "Get service iteration success": "backend.getServiceIterationSuccess",
    "You have an uncommitted service iteration in progress":
        "backend.uncommittedIterationInProgress",
    "Start service iteration success": "backend.startIterationSuccess",
    "New version is the same as current version":
        "backend.newVersionSameAsCurrent",
    "Commit service iteration success": "backend.commitIterationSuccess",
    "Update service description success": "backend.updateDescriptionSuccess",
    "You don't have permission to view all services":
        "backend.noPermissionViewAllServices",
    "You are not the owner of these services":
        "backend.notOwnerOfServices",
    "You don't have authorization to view other users' maintained services":
        "backend.noAuthViewMaintainedServices",
    "Get all categories success": "backend.getCategoriesSuccess",
    "Category name already exists": "backend.categoryNameExists",
    "Add category success": "backend.addCategorySuccess",
    "Category not found": "backend.categoryNotFound",
    "Category not belongs to this service iteration":
        "backend.categoryNotInIteration",
    "Category has apis, cannot delete": "backend.categoryHasApis",
    "Delete category success": "backend.deleteCategorySuccess",
    "Category name or description is required":
        "backend.categoryFieldRequired",
    "Category name or description not changed":
        "backend.categoryNotChanged",
    "Update category success": "backend.updateCategorySuccess",
    "Get all apis success": "backend.getApisSuccess",
    "Api not found": "backend.apiNotFound",
    "User not found": "backend.userNotFound",
    "You are neither the owner nor the maintainer of this service, nor the creator of this service iteration":
        "backend.notOwnerMaintainerOrIterationCreator",
    "Get api success": "backend.getApiSuccess",
    "Api category not changed": "backend.apiCategoryNotChanged",
    "Update api category success": "backend.updateApiCategorySuccess",
    "Category not belongs to this service": "backend.categoryNotInService",
    "Api method and name/path already exists in this service":
        "backend.apiAlreadyExists",
    "Add api success": "backend.addApiSuccess",
    "Api draft not found": "backend.apiDraftNotFound",
    "Api draft not belongs to this service iteration":
        "backend.apiDraftNotInIteration",
    "Copy api success": "backend.copyApiSuccess",
    "Delete api success": "backend.deleteApiSuccess",
    "Update api success": "backend.updateApiSuccess",
    "Invalid OpenAPI document: missing 'paths'":
        "backend.invalidOpenapiMissingPaths",
    "Swagger 2.0 is not supported yet": "backend.swagger2NotSupported",
    "Import OpenAPI to iteration success": "backend.importOpenapiSuccess",
    "Get user success": "backend.getUserSuccess",
    "Get users success": "backend.getUsersSuccess",
    "Wrong password": "backend.wrongPassword",
    "Login success": "backend.loginSuccess",
    "Username or email already registered": "backend.usernameOrEmailRegistered",
    "Register success": "backend.registerSuccess",
    "Wrong old password": "backend.wrongOldPassword",
    "New password cannot be the same as old password":
        "backend.newPasswordSameAsOld",
    "Modify password success": "backend.modifyPasswordSuccess",
};

const BACKEND_MESSAGE_PREFIXES: { prefix: string; key: string }[] = [
    { prefix: "Import OpenAPI failed:", key: "backend.importOpenapiFailed" },
    { prefix: "Failed to send email:", key: "backend.sendEmailFailed" },
];

/**
 * Resolve API response message to the current UI language.
 * Falls back to `fallbackKey` translation when message is missing or unknown.
 */
export function resolveApiMessage(
    message?: string | null,
    fallbackKey?: string,
): string {
    if (message) {
        const trimmed = message.trim();
        const key = BACKEND_MESSAGE_KEY_MAP[trimmed];
        if (key) return t(key);

        for (const { prefix, key: prefixKey } of BACKEND_MESSAGE_PREFIXES) {
            if (trimmed.startsWith(prefix)) {
                const detail = trimmed.slice(prefix.length).trim();
                return t(prefixKey, { detail });
            }
        }
    }

    if (fallbackKey) return t(fallbackKey);
    return message || "";
}

export function toastFromError(err: unknown, fallbackKey: string): string {
    if (err instanceof Error && err.message?.trim()) {
        const resolved = resolveApiMessage(err.message);
        return resolved || t(fallbackKey);
    }
    return t(fallbackKey);
}
