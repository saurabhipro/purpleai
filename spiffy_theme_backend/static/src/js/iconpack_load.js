/** @odoo-module **/

// # Part of Odoo Module Developed by Bizople Solutions Pvt. Ltd.
// # See LICENSE file for full copyright and licensing details.

import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";

export const SpiffyIconListView = {
   ...listView,
   buttonTemplate: "show_icon_pack",
};

registry.category("views").add("button_in_tree", SpiffyIconListView);