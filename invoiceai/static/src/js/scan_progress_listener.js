/** @odoo-module **/

import { registry } from "@web/core/registry";

const purpleAiNotificationService = {
    dependencies: ["bus_service"],
    start(env, { bus_service }) {
        // Correct implementation for Odoo 17/18
        bus_service.addChannel("purple_ai_notification");
        bus_service.subscribe("notification", (notifications) => {
            for (const { type, payload } of notifications) {
                if (type === "purple_ai_notification") {
                    env.bus.trigger("PURPLE_AI:SCAN_PROGRESS", payload);
                }
            }
        });
    },
};

registry.category("services").add("purple_ai_notification_service", purpleAiNotificationService);
