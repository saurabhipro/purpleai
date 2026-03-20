/** @odoo-module **/

import { Component } from "@odoo/owl";

export class WorkshopNode extends Component {
    static template = "jigsaw.WorkshopNode";
    static props = {
        node: Object,
        state: Object,
        onEdit: Function,
        onDelete: Function,
        onLine: Function,
        onComment: Function,
        onCommentKeydown: Function,
        submitComment: Function,
        hasComments: Boolean,
        isFiltered: Boolean,
        pos: Object,
    };

    get style() {
        const { pos } = this.props;
        let style = `left: ${pos.x}px; top: ${pos.y}px;`;
        if (pos.fill) {
            style += ` --node-fill: ${pos.fill};`;
        }
        return style;
    }
}
