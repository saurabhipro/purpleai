/** @odoo-module **/

import { Constants } from "./Constants";

// Map relationship color → arrowhead marker id
const COLOR_TO_MARKER = {
    '#2563eb': 'blue',
    '#059669': 'green',
    '#7c3aed': 'purple',
    '#d97706': 'amber',
    '#4f46e5': 'indigo',
    '#475569': 'slate',
    '#dc2626': 'red',
    '#b91c1c': 'red',
    '#db2777': 'pink',
    '#0d9488': 'teal',
};

export const Geometry = {

    /**
     * Returns the bounding geometry for a node shape.
     * Values must match the SVG shape dimensions in WorkshopCanvas.xml.
     *   cx / cy  — visual centre (for connection midpoints)
     *   topY     — y where a line entering from the top should connect
     *   botY     — y where a line leaving from the bottom should connect
     *   w / h    — overall bounding box width / height
     */
    nodeGeometry(node) {
        switch (node && node.type) {
            case 'individual':
                // ellipse cx=100 cy=46 rx=100 ry=46
                return { w: 200, h: 92, cx: 100, cy: 46, topY: 0, botY: 92 };
            case 'fund':
                // triangle: apex (110,4) base y=140, width 220
                return { w: 220, h: 140, cx: 110, cy: 90, topY: 30, botY: 140 };
            case 'trust':
                // shield path M 0,0 H 180 V 52 Q 90,90 0,52 Z
                return { w: 180, h: 90, cx: 90, cy: 32, topY: 0, botY: 82 };
            case 'asset':
                // diamond polygon 110,0 220,60 110,120 0,60
                return { w: 220, h: 120, cx: 110, cy: 60, topY: 0, botY: 120 };
            case 'gov':
                return { w: 180, h: 72, cx: 90, cy: 36, topY: 0, botY: 72 };
            case 'company':
            default:
                // rect 0,0 → 180,72
                return { w: 180, h: 72, cx: 90, cy: 36, topY: 0, botY: 72 };
        }
    },

    getLinkInfo(link, state) {
        if (!state.layout) return null;

        const sourcePos = state.layout[link.source.toString()];
        const targetPos = state.layout[link.target.toString()];
        if (!sourcePos || !targetPos) return null;

        const srcNode = state.nodes.find(n => n.id === link.source);
        const tgtNode = state.nodes.find(n => n.id === link.target);
        if (!srcNode || !tgtNode) return null;

        const srcGeo = this.nodeGeometry(srcNode);
        const tgtGeo = this.nodeGeometry(tgtNode);

        // ── Direction ─────────────────────────────────────────────────────────
        const srcCY = (sourcePos.y || 0) + srcGeo.cy;
        const tgtCY = (targetPos.y || 0) + tgtGeo.cy;
        const goingDown = tgtCY >= srcCY;

        // ── Source exit: always the node's bottom-centre (or top if going up) ──
        const sx = (sourcePos.x || 0) + srcGeo.cx;
        const sy = (sourcePos.y || 0) + (goingDown ? srcGeo.botY : srcGeo.topY);

        // ── Target entry: fanned across the node top so lines don't overlap ────
        //
        // When N links enter the same target node they are spread evenly so
        // each one enters at a distinct x position — like the "100% 100%"
        // example in the reference image.
        //
        // Fan spacing: 36px between adjacent lines, clamped to stay within
        // the node's horizontal bounds with 20px margin either side.
        const FAN_STEP = 36;

        const tgtLinks = state.links.filter(l => l.target === link.target);
        const tgtIdx = tgtLinks.indexOf(link);
        const tgtFan = tgtLinks.length;

        const tgtCenterX = (targetPos.x || 0) + tgtGeo.cx;
        const rawFanOff = (tgtIdx - (tgtFan - 1) / 2) * FAN_STEP;
        const maxFanOff = tgtGeo.cx - 20;                    // stay inside the node
        const fanOff = Math.max(-maxFanOff, Math.min(rawFanOff, maxFanOff));

        const tx = tgtCenterX + fanOff;
        const ty = (targetPos.y || 0) + (goingDown ? tgtGeo.topY : tgtGeo.botY);

        // ── Path ─────────────────────────────────────────────────────────────
        // Source exits centre-bottom → jog at midY → drops to fanned entry point.
        const midY = Math.round((sy + ty) / 2);
        const aligned = Math.abs(sx - tx) < 6;

        //  aligned → straight vertical
        //  offset  → M sx sy  V midY  H tx  V ty   (clean right-angle elbow)
        const d = aligned
            ? `M ${sx} ${sy} V ${ty}`
            : `M ${sx} ${sy} V ${midY} H ${tx} V ${ty}`;

        // ── Label positions ────────────────────────────────────────────────────
        // Place labels on the lower vertical leg (near the target) so they
        // don't overlap the junction elbow.
        const lx = tx - 6;                                // percent: left of lower leg
        const ly = Math.round((midY + ty) / 2);          // midpoint of lower leg

        const rx = tx + 6;                                // type: right of lower leg
        const ry = ly - 16;

        const typeInfo = Constants.RELATIONSHIP_TYPES[link.type] || Constants.RELATIONSHIP_TYPES.default;

        return {
            d,
            sx, sy,
            lx, ly,
            rx, ry,
            label: typeInfo.label,
            color: typeInfo.color,
            markerId: COLOR_TO_MARKER[typeInfo.color] || 'slate',
            percent: parseFloat(link.percent) || parseFloat(link.ownership_pct) || 0,
        };
    },
};
