/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class TenderAIDashboard extends Component {
    static template = "tender_ai.TenderAIDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            stats: {},
            lastUpdate: null,
            error: null,
        });

        onWillStart(async () => {
            await this.refresh();
        });
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const stats = await this.orm.call("tende_ai.dashboard", "get_stats", [], {});
            this.state.stats = stats || {};
            this.state.lastUpdate = new Date().toLocaleString();
        } catch (e) {
            this.state.error = e?.message || String(e);
        } finally {
            this.state.loading = false;
        }
    }

    _openActWindow({ title, resModel, domain = [] }) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: title,
            res_model: resModel,
            // Odoo web client expects `views` to be set for client-side actions
            // (otherwise it can crash with: action.views is undefined)
            views: [
                [false, "list"],
                [false, "form"],
            ],
            view_mode: "list,form",
            domain,
            target: "current",
        });
    }

    openJobs(domain = []) {
        this._openActWindow({ title: _t("Tender Jobs"), resModel: "tende_ai.job", domain });
    }

    openBidders() {
        this._openActWindow({ title: _t("Bidders"), resModel: "tende_ai.bidder", domain: [] });
    }

    openPayments() {
        this._openActWindow({ title: _t("Payments"), resModel: "tende_ai.payment", domain: [] });
    }

    openWorkExperience() {
        this._openActWindow({ title: _t("Work Experience"), resModel: "tende_ai.work_experience", domain: [] });
    }

    openTenders(domain = []) {
        this._openActWindow({ title: _t("Tenders"), resModel: "tende_ai.tender", domain });
    }
}

registry.category("actions").add("tender_ai.dashboard", TenderAIDashboard);


