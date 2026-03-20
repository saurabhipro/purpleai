/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

export class WorkshopModals extends Component {
    static template = "jigsaw.WorkshopModals";
    static props = {
        state: Object,
        onSaveEntity: Function,
        onSaveLink: Function,
        onDeleteLink: Function,
        onCloseEntityModal: Function,
        onCloseLinkModal: Function,
        onAddChild: Function,
        onAddParent: Function,
    };

    setup() {
        this.state = useState({
            activeTab: 'properties', // 'properties' or 'relationships'
        });
    }

    get editingNode() {
        return this.props.state.editingNode;
    }

    get parents() {
        if (!this.editingNode) return [];
        return this.props.state.links
            .filter(l => l.target === this.editingNode.id)
            .map(l => {
                const parent = this.props.state.nodes.find(n => n.id === l.source);
                return { ...l, node: parent };
            });
    }

    get children() {
        if (!this.editingNode) return [];
        return this.props.state.links
            .filter(l => l.source === this.editingNode.id)
            .map(l => {
                const child = this.props.state.nodes.find(n => n.id === l.target);
                return { ...l, node: child };
            });
    }
}
