# -*- coding: utf-8 -*-

from odoo import fields, models, _


class TenderAiJobChatWizard(models.TransientModel):
    _name = "tende_ai.job.chat.wizard"
    _description = "Tender AI Job Chat"

    job_id = fields.Many2one("tende_ai.job", required=True, readonly=True)
    question = fields.Text(string="Question", required=True)
    answer = fields.Text(string="Answer", readonly=True)
    model = fields.Char(string="Model", default="gemini-3-flash-preview")
    post_to_chatter = fields.Boolean(string="Post answer to chatter", default=True)

    def action_ask(self):
        self.ensure_one()

        from ..services.tender_chat_service import answer_job_question, post_chat_to_job_chatter

        res = answer_job_question(
            env=self.env,
            job_id=self.job_id.id,
            question=self.question,
            history=None,
            model=self.model,
        ) or {}

        self.answer = res.get("answer") or ""

        if self.post_to_chatter and res.get("success") and self.answer:
            post_chat_to_job_chatter(self.env, job_id=self.job_id.id, question=self.question, answer=self.answer)

        return {
            "type": "ir.actions.act_window",
            "name": _("Ask AI"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context),
        }


