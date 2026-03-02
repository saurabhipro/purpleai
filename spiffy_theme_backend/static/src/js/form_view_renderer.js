/** @odoo-module **/

// # Part of Odoo Module Developed by Bizople Solutions Pvt. Ltd.
// # See LICENSE file for full copyright and licensing details.

import { patch } from "@web/core/utils/patch";
import { FormController } from '@web/views/form/form_controller';

patch(FormController.prototype, {
    saveRecord: async function () {
        const changedFields = await this._super(...arguments);
        $('.tree_form_split > .o_view_controller > .o_control_panel .reload_view').click()
        return changedFields;
    },
});