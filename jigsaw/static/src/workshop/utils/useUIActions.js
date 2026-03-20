/** @odoo-module **/

import { Filtering } from "./Filtering";
import { Export } from "./Export";

/**
 * useUIActions — handles sidebar toggling, filter/ownership controls,
 * node selection, and data export for the Jigsaw workshop.
 *
 * @param {object}   state    - OWL reactive state from the parent component
 * @param {object}   services - { action, notification }
 */
export function useUIActions(state, services) {
    const { action } = services;

    // ── Navigation / App ──────────────────────────────────────────────────────

    function onClose() {
        action.doAction({ type: "ir.actions.act_window_close" });
    }

    // ── Sidebar & Tab Controls ────────────────────────────────────────────────

    function toggleSidebar(sidebar) {
        state.activeSidebar = state.activeSidebar === sidebar ? null : sidebar;
    }

    function toggleDataTab(tab) {
        state.activeDataTab = tab;
    }

    function onSelectNode(nodeId) {
        state.selectedNodeIds = [nodeId];
    }

    // ── Filter Controls ───────────────────────────────────────────────────────

    function isNodeFilteredOut(node) {
        return Filtering.isNodeFilteredOut(node, state);
    }

    function isLinkFilteredOut(link) {
        return Filtering.isLinkFilteredOut(link, state);
    }

    function toggleFilter(filter) {
        const idx = state.activeFilters.indexOf(filter);
        if (idx > -1) {
            state.activeFilters.splice(idx, 1);
        } else {
            state.activeFilters.push(filter);
        }
    }

    // ── Ownership Filter ──────────────────────────────────────────────────────

    function toggleOwnershipMenu() {
        state.showOwnershipMenu = !state.showOwnershipMenu;
        if (state.showOwnershipMenu) {
            updateOwnershipFilter();
        }
    }

    function setOwnershipDirection(dir) {
        state.ownershipDirection = dir;
        updateOwnershipFilter();
    }

    function clearOwnershipFilter() {
        state.ownershipVisibleNodeIds = [];
        state.showOwnershipMenu = false;
    }

    function updateOwnershipFilter() {
        state.ownershipVisibleNodeIds = Filtering.updateOwnershipFilter(state);
    }

    // ── Modal Helpers ─────────────────────────────────────────────────────────

    function onCloseEntityModal() {
        state.editingNode = null;
    }

    function onCloseLinkModal() {
        state.editingLink = null;
    }

    // ── Export ────────────────────────────────────────────────────────────────

    function exportExcel() {
        Export.exportExcel(state, (node, s) => Filtering.isNodeFilteredOut(node, s));
    }

    return {
        onClose,
        toggleSidebar,
        toggleDataTab,
        onSelectNode,
        isNodeFilteredOut,
        isLinkFilteredOut,
        toggleFilter,
        toggleOwnershipMenu,
        setOwnershipDirection,
        clearOwnershipFilter,
        updateOwnershipFilter,
        onCloseEntityModal,
        onCloseLinkModal,
        exportExcel,
    };
}
