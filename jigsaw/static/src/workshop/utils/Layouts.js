/** @odoo-module **/

import { Constants } from "./Constants";
import { Geometry } from "./Geometry";

export const Layouts = {
    treeLayout(state) {
        const childIds = new Set(state.links.map(l => l.target));
        let roots = state.nodes.filter(n => !childIds.has(n.id));

        if (roots.length === 0 && state.nodes.length > 0) {
            roots = [state.nodes[0]];
        }

        // levelOccupancy tracks the next available CENTRE-X for each level
        // (we position by centre so nodes of different widths line up perfectly)
        const levelNextCx = {};
        const levelHeight  = Constants.LEVEL_HEIGHT;
        const colSpacing   = Constants.NODE_HORIZONTAL_SPACING;
        const visited = new Set();
        const layout  = {};

        const getNode = id => state.nodes.find(n => n.id === id);

        const layoutStep = (nodeId, level) => {
            const sid = nodeId.toString();
            if (visited.has(sid)) return;
            visited.add(sid);

            const node = getNode(nodeId);
            const geo  = Geometry.nodeGeometry(node);

            if (levelNextCx[level] === undefined) {
                levelNextCx[level] = 200 + geo.cx;  // first node: start from 200px left-edge
            }

            // Centre-x for this node on this level
            const cx = levelNextCx[level];

            // Convert centre-x → top-left x  (layout stores top-left corner)
            const x = cx - geo.cx;
            const y = 100 + level * levelHeight;

            layout[sid] = { x, y };

            // Advance by the column spacing (measured from this centre to the next)
            levelNextCx[level] += colSpacing;

            // Recurse into children
            const children = state.links
                .filter(l => l.source === nodeId)
                .map(l => l.target);

            children.forEach(cid => layoutStep(cid, level + 1));
        };

        roots.forEach(root => layoutStep(root.id, 0));

        // Position any disconnected nodes
        state.nodes.forEach(n => {
            if (!visited.has(n.id.toString())) {
                layoutStep(n.id, 0);
            }
        });

        return layout;
    }
};
