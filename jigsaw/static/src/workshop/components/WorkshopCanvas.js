/** @odoo-module **/

import { Component } from "@odoo/owl";

export class WorkshopCanvas extends Component {
    static template = "jigsaw.WorkshopCanvas";
    static components = {};
    static props = {
        state: Object,
        getLinkInfo: Function,
        isNodeFilteredOut: Function,
        isLinkFilteredOut: Function,
        onEditEntity: Function,
        onDeleteEntity: Function,
        onLine: Function,
        onComment: Function,
        onCommentKeydown: Function,
        hasComments: Function,
        submitComment: Function,
    };
}
