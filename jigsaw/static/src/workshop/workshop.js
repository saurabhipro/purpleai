/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onWillUnmount, useState, useRef, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// Sub-components
import { WorkshopHeader } from "./components/WorkshopHeader";
import { WorkshopSidebar } from "./components/WorkshopSidebar";
import { WorkshopCanvas } from "./components/WorkshopCanvas";
import { WorkshopModals } from "./components/WorkshopModals";

// Utilities
import { Geometry } from "./utils/Geometry";
import { Constants } from "./utils/Constants";

// Hooks
import { useWorkshopInteractions } from "./utils/Interactions";
import { useEntityActions } from "./utils/useEntityActions";
import { useLayoutActions } from "./utils/useLayoutActions";
import { useCommentActions } from "./utils/useCommentActions";
import { useUIActions } from "./utils/useUIActions";

export class JigsawWorkshop extends Component {
    static template = "jigsaw.Workshop";
    static components = { WorkshopHeader, WorkshopSidebar, WorkshopCanvas, WorkshopModals };

    setup() {
        // ── Services ──────────────────────────────────────────────────────────
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");

        // ── Shared Reactive State ─────────────────────────────────────────────
        this.state = useState({
            nodes: [],
            links: [],
            layout: {},
            loading: true,
            zoom: Constants.DEFAULT_ZOOM,
            offsetX: Constants.DEFAULT_OFFSET_X,
            offsetY: Constants.DEFAULT_OFFSET_Y,
            selectedNodeIds: [],
            activeSidebar: "data",       // 'data' | 'comments' | null
            isSaving: false,
            showFilterMenu: false,
            showOwnershipMenu: false,
            ownershipDirection: "down",
            ownershipPctThreshold: 10,
            ownershipPctType: "more",
            ownershipFilterEnabled: false,
            ownershipVisibleNodeIds: [],
            filterText: "",
            filterType: "",
            activeFilters: [],
            comments: [],
            activeDataTab: "properties", // 'properties' | 'relationships' | 'files'
            showCommentInputForNode: null,
            newCommentText: "",
            showResolvedComments: false,
            showAllComments: true,
            contextMenu: { visible: false, x: 0, y: 0, nodeId: null, activeMenu: null },
            linkingNodeId: null,
            linkingMode: null,           // 'parent' | 'child'
            editingNode: null,
            editingLink: null,
        });

        // ── Refs & Diagram ID ─────────────────────────────────────────────────
        this.canvasRef = useRef("canvas");
        const rawId =
            this.props.action.params?.diagram_id ||
            this.props.action.context?.active_id ||
            this.props.action.context?.default_diagram_id ||
            this.props.action.res_id;
        this.diagramId = rawId ? parseInt(rawId) : null;

        // ── Hook: UI Actions ──────────────────────────────────────────────────
        // Initialised first because entity/layout hooks depend on isNodeFilteredOut
        const ui = useUIActions(this.state, {
            action: this.action,
            notification: this.notification,
        });
        Object.assign(this, ui);

        // ── Hook: Layout Actions ──────────────────────────────────────────────
        // Depends on isNodeFilteredOut from ui and saveLayout from entity (deferred via lambda)
        const layout = useLayoutActions(
            this.state,
            this.canvasRef,
            () => this.saveLayout(),          // deferred: saveLayout defined after entity hook
            (node) => this.isNodeFilteredOut(node)
        );
        Object.assign(this, layout);

        // ── Hook: Entity & Link Actions ───────────────────────────────────────
        const entity = useEntityActions(
            this.state,
            { orm: this.orm, action: this.action, notification: this.notification },
            this.diagramId,
            () => this.treeLayout()           // callback provided to ensureDefaultLayout
        );
        Object.assign(this, entity);

        // ── Hook: Comment Actions ─────────────────────────────────────────────
        const comments = useCommentActions(this.state);
        Object.assign(this, comments);

        // ── Lifecycle ─────────────────────────────────────────────────────────
        onWillStart(async () => {
            await this.loadData();
        });

        onMounted(() => {
            this.cleanupInteractions = useWorkshopInteractions(this.canvasRef, this.state, {
                onCreateLink: (id) => this.onCreateLink(id),
                updateOwnershipFilter: () => this.updateOwnershipFilter(),
                saveLayout: () => this.saveLayout(),
                onEditEntity: (id) => this.onEditEntity(id),
                onEditLink: (id) => this.onEditLink(id),
                notify: (msg, type) => this.notification.add(msg, { type }),
            });
        });

        onWillUnmount(() => {
            if (this.cleanupInteractions) this.cleanupInteractions();
        });
    }

    // ── Geometry (pass-through) ───────────────────────────────────────────────

    getLinkPath(link) {
        const info = this.getLinkInfo(link);
        return info ? info.d : "";
    }

    getLinkInfo(link) {
        return Geometry.getLinkInfo(link, this.state);
    }
}

registry.category("actions").add("jigsaw.workshop", JigsawWorkshop);
