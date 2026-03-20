/** @odoo-module **/

import { Component, onMounted, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Ringover Dialer Component - Robust Odoo 18 Implementation.
 */
export class RingoverDialer extends Component {
    static template = xml`<div class="o_ringover_dialer_container" style="display:none;"/>`;

    setup() {
        // In Odoo 18, useService MUST be imported from "@web/core/utils/hooks".
        this.ringover = useService("ringover_dialer");

        onMounted(() => {
            console.log("Ringover Dialer Component: Successfully mounted.");

            // Initialization of the service
            this.ringover.init();

            // Permanent global click listener
            document.addEventListener("click", (ev) => {
                const telLink = ev.target.closest('a[href^="tel:"]');
                if (telLink) {
                    let phoneNumber = telLink.getAttribute('href').replace(/^tel:/, '');
                    if (!phoneNumber && telLink.pathname) {
                        phoneNumber = telLink.pathname;
                    }

                    if (phoneNumber) {
                        ev.preventDefault();
                        ev.stopPropagation();
                        ev.stopImmediatePropagation();

                        this.ringover.dial(phoneNumber);
                    }
                }
            }, true);
        });
    }
}

registry.category("main_components").add("RingoverDialer", { Component: RingoverDialer });
