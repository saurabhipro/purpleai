/** @odoo-module **/

/**
 * useEntityActions — handles all data loading, entity CRUD, and
 * relationship (link) CRUD for the Jigsaw workshop.
 *
 * @param {object} state      - OWL reactive state from the parent component
 * @param {object} services   - { orm, action, notification }
 * @param {number} diagramId  - the current diagram's database ID
 * @param {Function} treeLayout - callback to run a tree layout (from useLayoutActions)
 */
export function useEntityActions(state, services, diagramId, treeLayout) {
    const { orm, action, notification } = services;

    // ── Data Loading ──────────────────────────────────────────────────────────

    async function loadData() {
        if (!diagramId) {
            console.error("No Diagram ID found in action or context");
            state.loading = false;
            return;
        }
        state.loading = true;
        try {
            const data = await orm.call("jigsaw.diagram", "get_diagram_data", [diagramId]);
            state.nodes = data.nodes;
            state.links = data.links;
            state.layout = data.layout;
            ensureDefaultLayout();
        } catch (e) {
            console.error(e);
        }
        state.loading = false;
    }

    function ensureDefaultLayout() {
        const hasLayout = Object.keys(state.layout).length > 0;
        if (!hasLayout) {
            treeLayout();
        } else {
            state.nodes.forEach((node, index) => {
                if (!state.layout[node.id]) {
                    state.layout[node.id] = {
                        x: 100 + (index * 50) % 500,
                        y: 100 + (index * 50) % 500,
                    };
                }
            });
        }
    }

    async function saveLayout() {
        state.isSaving = true;
        await orm.write("jigsaw.diagram", [diagramId], {
            layout_data: JSON.stringify(state.layout),
        });
        state.isSaving = false;
    }

    // ── Entity Actions ────────────────────────────────────────────────────────

    async function onAddEntity() {
        action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "jigsaw.entity",
                views: [[false, "form"]],
                target: "new",
                context: { default_diagram_id: diagramId },
            },
            { onClose: () => loadData() }
        );
    }

    async function onEditEntity(entityId) {
        const node = state.nodes.find((n) => n.id === entityId);
        if (node) state.editingNode = { ...node };
    }

    async function saveEntity() {
        if (!state.editingNode) return;
        const node = state.editingNode;
        await orm.write("jigsaw.entity", [node.id], {
            name: node.name,
            type: node.type,
            jurisdiction: node.jurisdiction,
            registration_no: node.registration_no,
            subtype: node.subtype,
            tax_id_number: node.tax_id_number,
            registered_office: node.registered_office,
            formation_date: node.formation_date,
            fund_family_name: node.fund_family_name,
            commitment_amount: node.commitment_amount,
            capital_contributed: node.capital_contributed,
        });

        const idx = state.nodes.findIndex((n) => n.id === node.id);
        if (idx !== -1) {
            state.nodes[idx] = { ...state.nodes[idx], ...node };
        }
        state.editingNode = null;
        notification.add("Entity updated", { type: "success" });
    }

    async function deleteEntity(entityId) {
        if (!confirm("Are you sure you want to delete this entity and all its relationships?")) return;

        await orm.unlink("jigsaw.entity", [entityId]);

        state.nodes = state.nodes.filter((n) => n.id !== entityId);
        state.links = state.links.filter(
            (l) => l.source !== entityId && l.target !== entityId
        );
        delete state.layout[entityId.toString()];

        await saveLayout();

        state.contextMenu.visible = false;
        state.editingNode = null;
        notification.add("Entity deleted", { type: "danger" });
    }

    async function updateEntityProperty(entityId, field, value) {
        try {
            await orm.write("jigsaw.entity", [entityId], { [field]: value });
            const node = state.nodes.find((n) => n.id === entityId);
            if (node) node[field] = value;
            notification.add(`Updated ${field}`, { type: "success" });
        } catch (e) {
            notification.add("Failed to update property", { type: "danger" });
        }
    }

    // ── Link / Relationship Actions ───────────────────────────────────────────

    function onEditLink(linkId) {
        const link = state.links.find(
            (l) => (l.id || `${l.source}-${l.target}`).toString() === linkId
        );
        if (link) state.editingLink = { ...link };
    }

    async function saveLink() {
        if (!state.editingLink) return;
        const link = state.editingLink;

        if (link.id) {
            await orm.write("jigsaw.relationship", [link.id], {
                type: link.type,
                percent: parseFloat(link.percent) || 0,
            });
        }

        const idx = state.links.findIndex(
            (l) => (l.id || `${l.source}-${l.target}`) === link.id
        );
        if (idx !== -1) {
            state.links[idx] = { ...state.links[idx], ...link };
        }
        state.editingLink = null;
        notification.add("Relationship updated", { type: "success" });
    }

    async function deleteLink(link) {
        if (!confirm("Remove this relationship?")) return;

        if (link.id) {
            await orm.unlink("jigsaw.relationship", [link.id]);
        }

        state.links = state.links.filter(
            (l) =>
                (l.id || `${l.source}-${l.target}`) !==
                (link.id || `${link.source}-${link.target}`)
        );
        state.editingLink = null;
        notification.add("Relationship removed", { type: "danger" });
    }

    async function onAddChild(parentId) {
        action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "jigsaw.relation",
                views: [[false, "form"]],
                target: "new",
                context: { default_source_entity_id: parentId },
            },
            { onClose: () => loadData() }
        );
    }

    async function onAddParent(childId) {
        action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "jigsaw.relation",
                views: [[false, "form"]],
                target: "new",
                context: { default_target_entity_id: childId },
            },
            { onClose: () => loadData() }
        );
    }

    function onLineClick(nodeId) {
        state.linkingNodeId = nodeId;
        notification.add("Select target entity to create link", { type: "info" });
    }

    async function onCreateLink(targetId) {
        const sourceId = state.linkingNodeId;
        if (sourceId === targetId) {
            state.linkingNodeId = null;
            return;
        }

        action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "jigsaw.relation",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_source_entity_id: sourceId,
                    default_target_entity_id: targetId,
                    default_relationship_type: "owns",
                },
            },
            {
                onClose: () => {
                    state.linkingNodeId = null;
                    loadData();
                },
            }
        );
    }

    return {
        loadData,
        saveLayout,
        onAddEntity,
        onEditEntity,
        saveEntity,
        deleteEntity,
        updateEntityProperty,
        onEditLink,
        saveLink,
        deleteLink,
        onAddChild,
        onAddParent,
        onLineClick,
        onCreateLink,
    };
}
