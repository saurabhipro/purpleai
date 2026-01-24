# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class TenderClientQuery(models.Model):
    _name = "tende_ai.client_query"
    _description = "Client Query (Eligibility)"
    _order = "asked_on desc, id desc"

    check_id = fields.Many2one(
        "tende_ai.bidder_check",
        string="Eligibility Check",
        required=True,
        ondelete="cascade",
        index=True,
    )
    job_id = fields.Many2one(
        "tende_ai.job",
        string="Job",
        related="check_id.job_id",
        store=True,
        readonly=True,
        index=True,
    )
    bidder_id = fields.Many2one(
        "tende_ai.bidder",
        string="Bidder",
        related="check_id.bidder_id",
        store=True,
        readonly=True,
        index=True,
    )

    asked_on = fields.Datetime(string="Date", default=fields.Datetime.now, required=True, index=True)
    asked_by = fields.Many2one("res.users", string="Asked By", default=lambda self: self.env.user, required=True)
    query = fields.Text(string="Client Query", required=True)
    internal_note = fields.Text(string="Internal Note / Response")

    state = fields.Selection(
        [("open", "Open"), ("answered", "Answered"), ("closed", "Closed")],
        string="Status",
        default="open",
        required=True,
        index=True,
    )

    @api.onchange("internal_note")
    def _onchange_internal_note(self):
        for rec in self:
            if rec.internal_note and rec.state == "open":
                rec.state = "answered"


