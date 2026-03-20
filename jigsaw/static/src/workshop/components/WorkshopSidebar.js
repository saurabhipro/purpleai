/** @odoo-module **/

import { Component } from "@odoo/owl";

export class WorkshopSidebar extends Component {
    static template = "jigsaw.WorkshopSidebar";
    static props = {
        state: Object,
        toggleSidebar: Function,
        toggleDataTab: Function,
        onUpdateProperty: Function,
        onDeleteEntity: Function,
        onAddChild: Function,
        onAddParent: Function,
        onSelectNode: Function,
    };
}
