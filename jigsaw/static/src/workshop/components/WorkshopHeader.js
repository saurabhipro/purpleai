/** @odoo-module **/

import { Component } from "@odoo/owl";

export class WorkshopHeader extends Component {
    static template = "jigsaw.WorkshopHeader";
    static props = {
        state: Object,
        onClose: Function,
        onExport: Function,
        onOrganize: Function,
        onFit: Function,
        onAddEntity: Function,
        toggleSidebar: Function,
        toggleOwnershipMenu: Function,
        setOwnershipDirection: Function,
        clearOwnershipFilter: Function,
        updateOwnershipFilter: Function,
        onZoomIn: Function,
        onZoomOut: Function,
    };
}
