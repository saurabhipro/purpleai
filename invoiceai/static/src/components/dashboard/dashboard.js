/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export class PurpleAIDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            stats: {
                active_info: { provider: '...', model: '...' },
                total_cost_inr: 0,
                total_requests: 0,
                invoice_buckets: { all: 0, hold: 0, validated: 0, passed_tally: 0, rejected: 0 },
                avg_time: 0,
                status_breakdown: { success: 0, error: 0 },
                providers: {},
                latest: []
            },
            loading: true,
        });

        // Explicitly bind to fix "this is undefined" error
        this.loadStats = this.loadStats.bind(this);
        this.openResults = this.openResults.bind(this);
        this.openInvoiceQueue = this.openInvoiceQueue.bind(this);

        onWillStart(async () => {
            await this.loadStats();
        });
    }

    async loadStats() {
        this.state.loading = true;
        try {
            const data = await this.orm.call("purple_ai.extraction_result", "get_dashboard_stats", []);
            this.state.stats = data;
        } catch (e) {
            console.error("Failed to load dashboard stats", e);
        } finally {
            this.state.loading = false;
        }
    }

    async openResults(domain = [], resId = false) {
        const action = {
            name: _t("Extraction Results"),
            type: "ir.actions.act_window",
            res_model: "purple_ai.extraction_result",
            domain: domain,
            target: "current",
        };
        
        if (resId) {
            action.res_id = resId;
            action.views = [[false, "form"]];
        } else {
            action.views = [[false, "list"], [false, "form"]];
        }
        
        this.action.doAction(action);
    }

    async openInvoiceQueue(name = "Invoices", domain = []) {
        const action = {
            name: _t(name),
            type: "ir.actions.act_window",
            res_model: "purple_ai.invoice_processor",
            domain: domain,
            views: [[false, "list"], [false, "form"]],
            target: "current",
        };
        this.action.doAction(action);
    }

    formatINR(val) {
        if (isNaN(val)) return '₹0.00';
        return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(val);
    }
}

PurpleAIDashboard.template = "invoiceai.AIDashboard";

registry.category("actions").add("invoiceai.dashboard", PurpleAIDashboard);
// Legacy tag from DB / bookmarks after module rename purpleai_invoices → invoiceai
registry.category("actions").add("purpleai_invoices.dashboard", PurpleAIDashboard);
