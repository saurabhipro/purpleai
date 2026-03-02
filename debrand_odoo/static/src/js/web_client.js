/** @odoo-module **/


import { WebClient } from "@web/webclient/webclient";
import { patch } from "@web/core/utils/patch";
import { useBus, useEffect, useService } from "@web/core/utils/hooks";
import { useOwnDebugContext } from "@web/core/debug/debug_context";
import { registry } from "@web/core/registry";
import { DebugMenu } from "@web/core/debug/debug_menu";
import { localization } from "@web/core/l10n/localization";
import { useTooltip } from "@web/core/tooltip/tooltip_hook";
import { Dialog } from "@web/core/dialog/dialog";
import { jsonrpc } from "@web/core/network/rpc_service";



import { Component, onMounted, onWillStart, useExternalListener, useState } from "@odoo/owl";


patch(WebClient.prototype, {
    
    setup() {
        this.menuService = useService("menu");
        this.actionService = useService("action");
        this.title = useService("title");
        this.router = useService("router");
        this.user = useService("user");
        useOwnDebugContext({ categories: ["default"] });
        if (this.env.debug) {
            registry.category("systray").add(
                "web.debug_mode_menu",
                {
                    Component: DebugMenu,
                },
                { sequence: 100 }
            );
        }
        this.localization = localization;
        this.state = useState({
            fullscreen: false,
        });
        this.title.setParts({ zopenerp: "Odoo" });
        useBus(this.env.bus, "ROUTE_CHANGE", this.loadRouterState);
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", ({ detail: mode }) => {
            if (mode !== "new") {
                this.state.fullscreen = mode === "fullscreen";
            }
        });
        onMounted(() => {
            this.loadRouterState();
            this.env.bus.trigger("WEB_CLIENT_READY");
        });
        useExternalListener(window, "click", this.onGlobalClick, { capture: true });
        onWillStart(this.registerServiceWorker);
        const self = this;

        jsonrpc(`/web/dataset/call_kw/res.config.settings/get_debranding_settings`, {
            model: "res.config.settings",
            method: "get_debranding_settings",
            args: [],
            kwargs: {},
        }).then(function(debranding_settings) {
            odoo.debranding_settings = debranding_settings;
            self.title.setParts({ zopenerp: debranding_settings && debranding_settings.title_brand });
            $("link[type='image/x-icon']").attr('href', odoo.debranding_settings.favicon_url)
            // $("link[rel='icon']").attr('href', odoo.debranding_settings.favicon_url)
            $("link[rel='apple-touch-icon']").attr('href', odoo.debranding_settings.favicon_url)
            localStorage.setItem('odoo_value', odoo.debranding_settings['odoo_text_replacement'],1);
            Dialog.defaultProps.title = odoo.debranding_settings.odoo_text_replacement
        });
    
        useTooltip();
    }

 
});


