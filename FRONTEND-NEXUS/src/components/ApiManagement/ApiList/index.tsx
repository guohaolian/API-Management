import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Tree, Input, Button, IconDelete } from "@cloud-materials/common";

import styles from "../index.module.less";
import { confirmAction } from "@/utils";
import { CloseIconCAM, OpenIconCAM } from "@/assets/icons";

const { Search } = Input;

function filterApiTreeData(treeData: any[], keyword: string): any[] {
    const kw = keyword.trim().toLowerCase();
    if (!kw) {
        return treeData;
    }
    return treeData
        .map((group) => {
            const categoryMatches = group.searchText?.includes(kw);
            const children = group.children ?? [];
            const filteredChildren = categoryMatches
                ? children
                : children.filter((child: any) =>
                      child.searchText?.includes(kw),
                  );
            if (filteredChildren.length === 0) {
                return null;
            }
            return { ...group, children: filteredChildren };
        })
        .filter(Boolean);
}

interface ApiListHandlers {
    handleUpdateApiCategory: (apiId: number, categoryId: number) => void;
    handleDeleteCategory: (categoryId: number) => void;
}

interface ApiListProps {
    inIteration: boolean;
    isLatest: boolean;
    autoSelectFirst?: boolean;
    selectedApiId: number;
    treeData: any[];
    handlers: ApiListHandlers;
    onSelectApi: (apiId: number) => void;
}

const ApiList: React.FC<ApiListProps> = (props) => {
    const { t } = useTranslation();
    const {
        inIteration,
        isLatest,
        autoSelectFirst = true,
        selectedApiId,
        treeData,
        handlers,
        onSelectApi,
    } = props;

    const { handleUpdateApiCategory, handleDeleteCategory } = handlers;

    const [searchKeyword, setSearchKeyword] = useState("");

    const filteredTreeData = useMemo(
        () => filterApiTreeData(treeData, searchKeyword),
        [treeData, searchKeyword],
    );

    const firstOptionKey = useMemo(
        () =>
            filteredTreeData.filter((item) => item.children?.length > 0)?.[0]
                ?.children?.[0]?.key || "",
        [filteredTreeData],
    );

    const categoryKeys = useMemo(() => {
        return (filteredTreeData || [])
            .map((item) => String(item?.key ?? ""))
            .filter((key) => key.startsWith("category-"));
    }, [filteredTreeData]);

    const firstOptionCategoryKey = useMemo(() => {
        if (!firstOptionKey) {
            return "";
        }
        for (const group of filteredTreeData || []) {
            const children = (group as any)?.children || [];
            if (
                Array.isArray(children) &&
                children.some((child: any) => String(child?.key) === firstOptionKey)
            ) {
                return String((group as any)?.key ?? "");
            }
        }
        return "";
    }, [filteredTreeData, firstOptionKey]);

    // 用于控制树节点选中状态
    const [selectedKeys, setSelectedKeys] = useState<string[]>([]);

    // 用于控制树节点展开/收起状态
    const [expandedKeys, setExpandedKeys] = useState<string[]>([]);

    const anyCategoryExpanded = useMemo(() => {
        return expandedKeys.some((key) => key.startsWith("category-"));
    }, [expandedKeys]);

    useEffect(() => {
        if (!autoSelectFirst || !firstOptionKey) {
            return;
        }
        onSelectApi(Number(firstOptionKey));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [autoSelectFirst, firstOptionKey]);

    useEffect(() => {
        if (selectedApiId > 0) {
            setSelectedKeys([String(selectedApiId)]);
        } else {
            setSelectedKeys([]);
        }
    }, [selectedApiId]);

    useEffect(() => {
        if (searchKeyword.trim()) {
            const keys = filteredTreeData
                .filter((group) => group.children?.length > 0)
                .map((group) => String(group.key));
            setExpandedKeys(keys);
        } else if (firstOptionCategoryKey) {
            setExpandedKeys([firstOptionCategoryKey]);
        }
    }, [searchKeyword, filteredTreeData, firstOptionCategoryKey]);

    const handleToggleAllCategories = () => {
        setExpandedKeys(anyCategoryExpanded ? [] : categoryKeys);
    };

    const handleSelectApi = (keys: string[]) => {
        const apiId = Number(keys[0]);
        if (Number.isNaN(apiId) || apiId <= 0) {
            onSelectApi(-1);
            return;
        }
        if (apiId === selectedApiId) {
            return;
        }
        onSelectApi(apiId);
    };

    const handleDrag = (info: any) => {
        // 迭代过程中不可拖拽 API 更换分类
        if (inIteration) {
            return;
        }
        // 历史版本 API 不可拖拽更换分类
        if (!isLatest) {
            return;
        }
        const { dragNode, dropNode } = info;
        const apiId = Number(dragNode.key);
        let categoryId = -1;
        if (dropNode.key.startsWith("category-")) {
            // 若拖拽目标是分类节点，直接使用分类 ID
            if (dropNode.key === "category-null") {
                // 若拖拽目标是未分类节点，分类 ID 设为 -1
                categoryId = -1;
            } else {
                categoryId = Number(dropNode.key.replace("category-", ""));
            }
        } else {
            // 若拖拽目标不是分类节点，获取其父分类 ID
            const category = dropNode.props.parentKey;
            if (!category || !category.startsWith("category-")) {
                return;
            }
            if (category === "category-null") {
                // 若拖拽目标是未分类节点，分类 ID 设为 -1
                categoryId = -1;
            } else {
                categoryId = Number(category.replace("category-", ""));
            }
        }
        if (!apiId || apiId === Number.NaN) {
            return;
        }
        // 若当前 API 已属于该分类，无需更新
        if (
            dragNode.props.parentKey === dropNode.key ||
            dragNode.props.parentKey === dropNode.props.parentKey
        ) {
            return;
        }
        handleUpdateApiCategory(apiId, categoryId);
    };

    if (!treeData || treeData.length === 0) {
        return null;
    }

    return (
        <div style={{ padding: 12 }}>
            <div className={styles.search}>
                <Search
                    allowClear
                    placeholder={t("apiManagement.searchApi")}
                    value={searchKeyword}
                    onChange={setSearchKeyword}
                />
                <Button
                    type="outline"
                    shape="square"
                    size="mini"
                    title={
                        anyCategoryExpanded
                            ? t("apiManagement.collapseAll")
                            : t("apiManagement.expandAll")
                    }
                    onClick={handleToggleAllCategories}
                    style={{
                        width: 28,
                        minWidth: 28,
                        height: 28,
                        padding: 0,
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                    }}
                    icon={
                        <img
                            src={anyCategoryExpanded ? CloseIconCAM : OpenIconCAM}
                            alt={anyCategoryExpanded ? "collapse" : "expand"}
                            width={14}
                            height={14}
                        />
                    }
                />
            </div>

            {/* autoExpandParent只有在Tree初次挂载时生效，所以要在treeData计算完成后再渲染 */}
            {filteredTreeData.length > 0 ? (
                <Tree
                    className={styles.tree}
                    selectedKeys={selectedKeys}
                    treeData={filteredTreeData}
                    autoExpandParent
                    expandedKeys={expandedKeys}
                    blockNode
                    actionOnClick={["select", "expand"]}
                    draggable={!inIteration && isLatest}
                    onSelect={handleSelectApi}
                    onExpand={(keys) => setExpandedKeys((keys || []).map(String))}
                    onDrop={handleDrag}
                    // 删除分类按钮
                    renderExtra={(node) => {
                        const isCategoryNode =
                            !node.draggable &&
                            !node.selectable &&
                            node._key !== "category-null";
                        const isEmptyCategory =
                            isCategoryNode && !node.childrenData?.length;
                        const canDeleteCategory =
                            isEmptyCategory ||
                            (inIteration && isCategoryNode);
                        if (!canDeleteCategory) {
                            return null;
                        }
                        return (
                            <Button
                                onClick={() =>
                                    confirmAction(
                                        () =>
                                            handleDeleteCategory(
                                                Number(
                                                    node?._key?.replace(
                                                        "category-",
                                                        ""
                                                    ) ?? -1
                                                )
                                            ),
                                        "action.delete",
                                        inIteration
                                            ? "confirm.deleteCategoryWithApis"
                                            : "confirm.deleteCategory",
                                        { danger: true },
                                    )
                                }
                                type="outline"
                                status="danger"
                                shape="circle"
                                size="mini"
                                className={styles.nodeDelete}
                                style={{
                                    width: 20,
                                    height: 20,
                                    position: "absolute",
                                    top: 0,
                                    right: 0,
                                }}
                                icon={<IconDelete />}
                            />
                        );
                    }}
                />
            ) : (
                searchKeyword.trim() && (
                    <div style={{ color: "#86909c", textAlign: "center", padding: 16 }}>
                        {t("apiManagement.noMatchingApi")}
                    </div>
                )
            )}
        </div>
    );
};

export default ApiList;
