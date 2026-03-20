/** @odoo-module **/

import { Constants } from "./Constants";
import { Layouts } from "./Layouts";
import { Geometry } from "./Geometry";

/**
 * useLayoutActions — handles all canvas viewport controls:
 * tree layout, organise, fit-to-screen, zoom, and node style.
 */
export function useLayoutActions(state, canvasRef, saveLayout, isNodeFilteredOut) {

    // ── Layout Computation ────────────────────────────────────────────────────

    function treeLayout() {
        const layout = Layouts.treeLayout(state);
        state.layout = { ...state.layout, ...layout };
    }

    async function organizeLayout() {
        state.layout = {};
        treeLayout();
        state.offsetX = Constants.DEFAULT_OFFSET_X;
        state.offsetY = Constants.DEFAULT_OFFSET_Y;
        state.zoom = Constants.DEFAULT_ZOOM;
        await saveLayout();
    }

    // ── Fit to Screen ─────────────────────────────────────────────────────────

    function fitToScreen() {
        const canvas = canvasRef.el;
        if (!canvas) return;

        const visibleNodes = state.nodes.filter((n) => !isNodeFilteredOut(n));
        if (visibleNodes.length === 0) return;

        const PADDING = 80;
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

        visibleNodes.forEach((node) => {
            const pos = state.layout[node.id.toString()];
            if (!pos) return;
            // Use accurate per-type bounding box from Geometry
            const geo = Geometry.nodeGeometry(node);

            minX = Math.min(minX, pos.x);
            minY = Math.min(minY, pos.y);
            maxX = Math.max(maxX, pos.x + geo.w);
            maxY = Math.max(maxY, pos.y + geo.h);
        });

        if (minX === Infinity) return;

        const contentW = maxX - minX;
        const contentH = maxY - minY;
        const canvasW = canvas.clientWidth;
        const canvasH = canvas.clientHeight;

        const availW = canvasW - PADDING * 2;
        const availH = canvasH - PADDING * 2;

        const zoomX = availW / contentW;
        const zoomY = availH / contentH;
        const newZoom = Math.max(
            Constants.MIN_ZOOM,
            Math.min(Constants.MAX_ZOOM, Math.min(zoomX, zoomY))
        );

        const scaledW = contentW * newZoom;
        const scaledH = contentH * newZoom;

        state.zoom = newZoom;
        state.offsetX = (canvasW - scaledW) / 2 - minX * newZoom;
        state.offsetY = (canvasH - scaledH) / 2 - minY * newZoom;
    }

    // ── Node Color (persisted via layout.fill) ────────────────────────────────

    async function updateNodeColor(color) {
        const id = state.contextMenu.nodeId;
        if (!id) return;
        const sid = id.toString();
        if (!state.layout[sid]) {
            state.layout[sid] = { x: 100, y: 100 };
        }
        state.layout[sid].fill = color;
        saveLayout();
        state.contextMenu.visible = false;
        state.contextMenu.activeMenu = null;
    }

    // ── Zoom Controls ─────────────────────────────────────────────────────────

    function onZoomIn() {
        state.zoom = Math.min(Constants.MAX_ZOOM, state.zoom + Constants.ZOOM_STEP);
    }

    function onZoomOut() {
        state.zoom = Math.max(Constants.MIN_ZOOM, state.zoom - Constants.ZOOM_STEP);
    }

    return {
        treeLayout,
        organizeLayout,
        fitToScreen,
        updateNodeColor,
        onZoomIn,
        onZoomOut,
    };
}
