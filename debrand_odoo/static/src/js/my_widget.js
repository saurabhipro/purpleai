/** @odoo-module */

import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component } from "@odoo/owl";

export class ResConfigEdition extends Component {
    setup() {
        super.setup();
        this.server_version = session.server_version;
        if(odoo && odoo.debranding_settings && odoo.debranding_settings.odoo_text_replacement)
            this.odoo_text_replacement = odoo.debranding_settings.odoo_text_replacement;
            
        else
            this.odoo_text_replacement = "Software"
    }
}
ResConfigEdition.props = {
    ...standardWidgetProps,
};
ResConfigEdition.template = "debrand_odoo.res_config_edition";

export const resConfigEdition = {
    component: ResConfigEdition,
};
registry.category("view_widgets").add("res_config_editions", resConfigEdition);
