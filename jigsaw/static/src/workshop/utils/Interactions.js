/** @odoo-module **/

/**
 * useWorkshopInteractions — attaches mouse/keyboard/wheel event handlers
 * to the canvas wrapper for drag, pan, zoom, context-menu, and linking.
 *
 * Nodes are now SVG <g class="jigsaw-node"> elements inside an <svg>.
 * We use closest('[data-id]') to find the hit node since <g> supports closest().
 */
export function useWorkshopInteractions(canvasRef, state, callbacks) {
    let isDragging = false;
    let lastX, lastY;
    let draggedNode = null;
    let isPanning = false;

    function getNodeElement(target) {
        // SVG <g data-id="..."> — works with closest on SVG elements
        return target.closest('[data-id]');
    }

    const onMouseDown = (e) => {
        const nodeElement = getNodeElement(e.target);
        if (nodeElement) {
            const id = parseInt(nodeElement.dataset.id);

            if (state.linkingNodeId) {
                callbacks.onCreateLink(id);
                lastX = e.clientX;
                lastY = e.clientY;
                return;
            }

            const closestNode = state.nodes.find(n => n.id === id);

            if (closestNode) {
                if (!e.ctrlKey && !e.shiftKey && !e.metaKey) {
                    state.selectedNodeIds = [closestNode.id];
                } else {
                    if (state.selectedNodeIds.includes(closestNode.id)) {
                        state.selectedNodeIds = state.selectedNodeIds.filter(sid => sid !== closestNode.id);
                    } else {
                        state.selectedNodeIds.push(closestNode.id);
                    }
                }
                if (state.showOwnershipMenu) {
                    callbacks.updateOwnershipFilter();
                }
            }
            draggedNode = closestNode;
            isDragging = true;
        } else {
            state.selectedNodeIds = [];
            if (state.linkingNodeId) {
                state.linkingNodeId = null;
                callbacks.notify("Linking cancelled", "secondary");
            }
            isPanning = true;
        }
        lastX = e.clientX;
        lastY = e.clientY;
    };

    const onMouseMove = (e) => {
        if (!isDragging && !isPanning) return;
        const dx = (e.clientX - lastX) / state.zoom;
        const dy = (e.clientY - lastY) / state.zoom;

        if (isDragging && draggedNode) {
            state.selectedNodeIds.forEach(nodeId => {
                const sid = nodeId.toString();
                if (!state.layout[sid]) {
                    state.layout[sid] = { x: 100, y: 100 };
                }
                state.layout[sid].x += dx;
                state.layout[sid].y += dy;
            });
        } else if (isPanning) {
            state.offsetX += dx * state.zoom;
            state.offsetY += dy * state.zoom;
        }

        lastX = e.clientX;
        lastY = e.clientY;
    };

    const onMouseUp = () => {
        if (isDragging) {
            callbacks.saveLayout();
        }
        isDragging = false;
        isPanning = false;
        draggedNode = null;
    };

    const onKeyDown = (e) => {
        if (e.key === 'Escape' && state.linkingNodeId) {
            state.linkingNodeId = null;
            callbacks.notify("Linking cancelled", "secondary");
        }
    };

    const onContextMenu = (e) => {
        const nodeElement = getNodeElement(e.target);
        if (nodeElement) {
            e.preventDefault();
            const id = parseInt(nodeElement.dataset.id);
            state.contextMenu.visible = true;
            state.contextMenu.x = e.clientX;
            state.contextMenu.y = e.clientY;
            state.contextMenu.nodeId = id;
            state.contextMenu.activeMenu = null;

            if (!state.selectedNodeIds.includes(id)) {
                state.selectedNodeIds = [id];
            }
        } else {
            state.contextMenu.visible = false;
        }
    };

    const onDblClick = (e) => {
        const nodeElement = getNodeElement(e.target);
        if (nodeElement) {
            const id = parseInt(nodeElement.dataset.id);
            callbacks.onEditEntity(id);
            return;
        }

        // Double-click on a link label
        const labelElement = e.target.closest('[data-link-id]');
        if (labelElement) {
            const linkId = labelElement.dataset.linkId;
            callbacks.onEditLink(linkId);
        }
    };

    const onClick = (e) => {
        if (state.contextMenu.visible && !e.target.closest('.jigsaw-context-menu')) {
            state.contextMenu.visible = false;
        }
    };

    const onWheel = (e) => {
        if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            state.zoom = Math.max(0.1, Math.min(2, state.zoom * delta));
        }
    };

    // Attach listeners
    canvasRef.el.addEventListener("mousedown", onMouseDown);
    canvasRef.el.addEventListener("contextmenu", onContextMenu);
    canvasRef.el.addEventListener("dblclick", onDblClick);
    canvasRef.el.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    window.addEventListener("click", onClick);
    window.addEventListener("keydown", onKeyDown);

    // Return cleanup function
    return () => {
        canvasRef.el.removeEventListener("mousedown", onMouseDown);
        canvasRef.el.removeEventListener("contextmenu", onContextMenu);
        canvasRef.el.removeEventListener("dblclick", onDblClick);
        canvasRef.el.removeEventListener("wheel", onWheel);
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
        window.removeEventListener("click", onClick);
        window.removeEventListener("keydown", onKeyDown);
    };
}
