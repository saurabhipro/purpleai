from odoo import models, fields, api, _

class AuditDashboard(models.Model):
    _name = 'audit.dashboard'
    _description = 'Audit Tool Dashboard'
    
    name = fields.Char(string="Name", default="Audit Dashboard")

    # KPI Fields
    total_memos = fields.Integer(compute='_compute_stats')
    draft_memos = fields.Integer(compute='_compute_stats')
    pending_partner = fields.Integer(compute='_compute_stats')
    in_progress = fields.Integer(compute='_compute_stats')
    pending_review = fields.Integer(compute='_compute_stats')
    approved = fields.Integer(compute='_compute_stats')
    rejected = fields.Integer(compute='_compute_stats')

    @api.model
    def action_open_dashboard(self):
        """ Returns the dashboard action, creating the record if needed """
        dashboard = self.search([], limit=1)
        if not dashboard:
            dashboard = self.create({'name': 'Audit Dashboard'})
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Audit Dashboard',
            'res_model': 'audit.dashboard',
            'res_id': dashboard.id,
            'view_mode': 'form',
            'view_id': self.env.ref('audit_tool.view_audit_dashboard_form').id,
            'target': 'current',
        }

    def _compute_stats(self):
        for rec in self:
            Memo = self.env['audit.memo']
            rec.total_memos = Memo.search_count([])
            rec.draft_memos = Memo.search_count([('state', '=', 'draft')])
            rec.pending_partner = Memo.search_count([('state', '=', 'partner_review')])
            rec.in_progress = Memo.search_count([('state', '=', 'in_progress')])
            rec.pending_review = Memo.search_count([('state', 'in', ['level_1_review', 'final_review', 'npsg_assignment'])])
            rec.approved = Memo.search_count([('state', '=', 'approved')])
            rec.rejected = Memo.search_count([('state', '=', 'rejected')])

    def action_open_draft(self):
        return self._get_action('Step 1: Draft', [('state', '=', 'draft')])

    def action_open_pending_partner(self):
        return self._get_action('Step 2: Partner Review', [('state', '=', 'partner_review')])

    def action_open_in_progress(self):
        return self._get_action('Step 4: In Progress', [('state', '=', 'in_progress')])
        
    def action_open_review(self):
         return self._get_action('Pending Review', [('state', 'in', ['level_1_review', 'final_review', 'npsg_assignment'])])

    def action_open_approved(self):
        return self._get_action('Approved', [('state', '=', 'approved')])

    def action_open_rejected(self):
        return self._get_action('Rejected', [('state', '=', 'rejected')])

    def _get_action(self, name, domain):
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'audit.memo',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
        }
