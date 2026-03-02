/** @odoo-module **/

// # Part of Odoo Module Developed by Bizople Solutions Pvt. Ltd.
// # See LICENSE file for full copyright and licensing details.

import { patch } from "@web/core/utils/patch";
import { SwitchCompanyMenu } from "@web/webclient/switch_company_menu/switch_company_menu";
import { registry } from "@web/core/registry";

patch(SwitchCompanyMenu.prototype, {
    setup() {
        super.setup();
        this.isDebug = Boolean(odoo.debug);
        this.isAssets = odoo.debug.includes("assets");
        this.isTests = odoo.debug.includes("tests");
    },
});

// show company menu even if company is count is 1 
const systrayItemSwitchCompanyMenu = {
    Component: SwitchCompanyMenu,
    isDisplayed(env) {
        const { allowedCompanies } = env.services.company;
        return Object.keys(allowedCompanies).length > 0;
    },
};

registry.category("systray").add("SwitchCompanyMenu", systrayItemSwitchCompanyMenu, { sequence: 1, force: true });