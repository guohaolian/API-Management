import { useEffect, useMemo, useState } from "react";
import {
    Tree,
    Input,
    Dropdown,
    Menu,
    Button,
    IconDelete,
} from "@cloud-materials/common";

import styles from "../index.module.less";
import { handleConfirm, inIterationWarning } from "@/utils";
import { CloseIconCAM, OpenIconCAM } from "@/assets/icons";

const { Search } = Input;

interface ApiListHandlers {
    handleAddApi: () => void;
    handleAddCategory: () => void;
    handleUpdateApiCategory: (apiId: number, categoryId: number) => void;
    handleDeleteCategory: (categoryId: number) => void;
    handleStartIteration: () => void;
    handleCompleteIteration: () => void;
}

interface ApiListProps {
    inIteration: boolean;
    isLatest: boolean;
    treeData: any[];
    handlers: ApiListHandlers;
    setSelectedApiId: (apiId: number) => void;
}

const ApiList: React.FC<ApiListProps> = (props) => {
    const { inIteration, isLatest, treeData, handlers, setSelectedApiId } =
        props;

    const {
        handleAddApi,
        handleAddCategory,
        handleUpdateApiCategory,
        handleDeleteCategory,
        handleStartIteration,
        handleCompleteIteration,
    } = handlers;

    const firstOptionKey = useMemo(
        () =>
            treeData.filter((item) => item.children?.length > 0)?.[0]
                ?.children?.[0]?.key || "",
        [treeData]
    );

    const categoryKeys = useMemo(() => {
        return (treeData || [])
            .map((item) => String(item?.key ?? ""))
            .filter((key) => key.startsWith("category-"));
    }, [treeData]);

    const firstOptionCategoryKey = useMemo(() => {
        if (!firstOptionKey) {
            return "";
        }
        for (const group of treeData || []) {
            const children = (group as any)?.children || [];
            if (
                Array.isArray(children) &&
                children.some((child: any) => String(child?.key) === firstOptionKey)
            ) {
                return String((group as any)?.key ?? "");
            }
        }
        return "";
    }, [treeData, firstOptionKey]);

    // 用于控制树节点选中状态
    const [selectedKeys, setSelectedKeys] = useState<string[]>([]);

    // 用于控制树节点展开/收起状态
    const [expandedKeys, setExpandedKeys] = useState<string[]>([]);

    const anyCategoryExpanded = useMemo(() => {
        return expandedKeys.some((key) => key.startsWith("category-"));
    }, [expandedKeys]);

    useEffect(() => {
        if (!firstOptionKey) {
            return;
        }
        setSelectedApiId(Number(firstOptionKey));
        setSelectedKeys([firstOptionKey]);
    }, [firstOptionKey]);

    useEffect(() => {
        if (!firstOptionCategoryKey) {
            return;
        }
        // 默认展开包含当前选中 API 的分类，避免选中节点不可见
        setExpandedKeys([firstOptionCategoryKey]);
    }, [firstOptionCategoryKey]);

    const handleToggleAllCategories = () => {
        setExpandedKeys(anyCategoryExpanded ? [] : categoryKeys);
    };

    const otherOperations = (
        <Menu style={{ width: 100 }}>
            <Menu.Item key="1" onClick={handleAddCategory}>
                添加分类
            </Menu.Item>
        </Menu>
    );

    const inIterationOperations = (
        <Menu style={{ width: 100 }}>
            <Menu.Item key="1" onClick={handleAddApi}>
                创建 API
            </Menu.Item>
        </Menu>
    );

    const handleSelectApi = (keys: string[]) => {
        inIterationWarning(
            () => {
                const apiId = Number(keys[0]);
                if (Number.isNaN(apiId) || apiId <= 0) {
                    setSelectedApiId(-1);
                    return;
                }
                setSelectedApiId(apiId);
                setSelectedKeys(keys);
            },
            inIteration,
            "warning"
        );
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
                <Search allowClear placeholder="搜索 API" />
                <Button
                    type="outline"
                    shape="square"
                    size="mini"
                    title={anyCategoryExpanded ? "一键收起" : "一键展开"}
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
                {inIteration ? (
                    <Dropdown.Button
                        type="outline"
                        droplist={inIterationOperations}
                        position="bl"
                        trigger="click"
                        onClick={handleCompleteIteration}
                    >
                        完成迭代
                    </Dropdown.Button>
                ) : (
                    isLatest && (
                        <Dropdown.Button
                            type="outline"
                            droplist={otherOperations}
                            position="bl"
                            trigger="click"
                            onClick={() =>
                                handleConfirm(
                                    handleStartIteration,
                                    "开始迭代",
                                    "确认开始新的迭代？"
                                )
                            }
                        >
                            发起迭代
                        </Dropdown.Button>
                    )
                )}
            </div>

            {/* autoExpandParent只有在Tree初次挂载时生效，所以要在treeData计算完成后再渲染 */}
            {treeData.length > 0 && (
                <Tree
                    className={styles.tree}
                    selectedKeys={selectedKeys}
                    treeData={treeData}
                    autoExpandParent
                    expandedKeys={expandedKeys}
                    blockNode
                    draggable={!inIteration && isLatest}
                    onSelect={handleSelectApi}
                    onExpand={(keys) => setExpandedKeys((keys || []).map(String))}
                    onDrop={handleDrag}
                    // 删除分类按钮
                    renderExtra={(node) => {
                        if (
                            !node.draggable &&
                            !node.selectable &&
                            !node.childrenData?.length &&
                            node._key !== "category-null"
                        ) {
                            // 没有子节点的 category 节点（不包括未分类节点）
                            return (
                                <Button
                                    onClick={() =>
                                        handleConfirm(
                                            () =>
                                                handleDeleteCategory(
                                                    Number(
                                                        node?._key?.replace(
                                                            "category-",
                                                            ""
                                                        ) ?? -1
                                                    )
                                                ),
                                            "删除",
                                            "确认删除当前分类？"
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
                        }
                        return null;
                    }}
                />
            )}
        </div>
    );
};

export default ApiList;
