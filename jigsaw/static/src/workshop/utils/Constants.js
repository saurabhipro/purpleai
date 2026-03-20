/** @odoo-module **/

export const Constants = {
    // Canvas & Geometry
    NODE_WIDTH: 180,       // default (company/gov) node SVG width
    ENTRY_FAN_GAP: 20,
    RAIL_GAP: 22,
    MIN_GAP: 35,
    VERTICAL_THRESHOLD: 30,

    // Layout
    LEVEL_HEIGHT: 280,
    NODE_HORIZONTAL_SPACING: 300,
    DEFAULT_OFFSET_X: 200,
    DEFAULT_OFFSET_Y: 100,
    DEFAULT_ZOOM: 0.8,

    // Node Heights by Type — must match SVG shape heights in WorkshopCanvas.xml
    NODE_HEIGHTS: {
        company:    72,
        gov:        72,
        individual: 92,
        fund:      140,
        trust:      90,
        asset:     120,
        default:    72,
    },

    // Relationship Styles
    RELATIONSHIP_TYPES: {
        owns: { label: 'OWNS', color: '#2563eb' },
        controls: { label: 'CONTROLS', color: '#059669' },
        director: { label: 'DIRECTOR', color: '#7c3aed' },
        beneficiary: { label: 'BENEFICIARY', color: '#d97706' },
        trustee: { label: 'TRUSTEE', color: '#4f46e5' },
        reports: { label: 'REPORTS', color: '#475569' },
        transferred: { label: 'TRANSFERRED', color: '#dc2626' },
        guarantees: { label: 'GUARANTEES', color: '#db2777' },
        partner: { label: 'PARTNER', color: '#0d9488' },
        litigates: { label: 'LITIGATES', color: '#b91c1c' },
        default: { label: 'LINK', color: '#64748b' }
    },

    // UI Defaults
    MAX_ZOOM: 2.0,
    MIN_ZOOM: 0.1,
    ZOOM_STEP: 0.1,
    ZOOM_SENSITIVITY: 0.9, // for scroll wheel
};
