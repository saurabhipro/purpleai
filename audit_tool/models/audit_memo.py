from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AuditMemo(models.Model):
    _name = 'audit.memo'
    _description = 'Audit Memo/Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    subject = fields.Char(string='Subject', required=True, tracking=True)
    description = fields.Html(string='Description', required=True)
    
    state = fields.Selection([
        ('draft', 'Step 1: Draft'),
        ('partner_review', 'Step 2: Partner Review'),
        ('npsg_assignment', 'Step 3: NPSG Assignment'),
        ('in_progress', 'Step 4: In Progress (Preparer)'),
        ('level_1_review', 'Step 5: First Level Review'),
        ('final_review', 'Step 6: Final Review'),
        ('approved', 'Step 7: Approved'),
        ('rejected', 'Rejected'),
        ('on_hold', 'On Hold'),
    ], string='Status', default='draft', tracking=True, group_expand='_expand_states')

    # Users involved
    engagement_team_user_id = fields.Many2one('res.users', string='Engagement Team Member', default=lambda self: self.env.user, tracking=True)
    engagement_partner_id = fields.Many2one('res.users', string='Engagement Partner', tracking=True)
    npsg_user_id = fields.Many2one('res.users', string='NPSG Team Member', tracking=True)
    preparer_id = fields.Many2one('res.users', string='Preparer', tracking=True)
    reviewer_1_id = fields.Many2one('res.users', string='First Level Reviewer', tracking=True)
    reviewer_final_id = fields.Many2one('res.users', string='Final Reviewer', tracking=True)

    # Documents
    document_ids = fields.One2many('audit.document', 'memo_id', string='Documents')

    # Kanban & Dashboard fields
    color = fields.Integer('Color Index')
    priority = fields.Selection([('0', 'Normal'), ('1', 'Low'), ('2', 'High'), ('3', 'Urgent')], default='0', string="Priority")
    kanban_state = fields.Selection([('normal', 'In Progress'), ('done', 'Ready'), ('blocked', 'Blocked')], default='normal')

    # Content Fields
    facts_of_case = fields.Html(string='Understanding of Facts of the Case')
    npsg_research = fields.Html(string='NPSG Research')
    npsg_views = fields.Html(string='NPSG Views')
    additional_info = fields.Text(string='Additional Information')

    # Custom Form Builder Fields
    custom_field_ids = fields.One2many('audit.memo.custom.field', 'memo_id', string="Custom Fields")

    @api.model
    def default_get(self, fields_list):
        defaults = super(AuditMemo, self).default_get(fields_list)
        if 'custom_field_ids' in fields_list:
            # Pre-fill with active definitions
            definitions = self.env['audit.form.definition'].search([])
            lines = []
            for definition in definitions:
                lines.append((0, 0, {
                    'definition_id': definition.id,
                }))
            defaults['custom_field_ids'] = lines
        return defaults

    @api.model
    def create(self, vals):
        # Ensure name creation 
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('audit.memo') or _('New')
        
        # Ensure Custom Fields are created if not present (e.g. via API or strict create)
        # Note: We can't easily iterate Definitions here without checking vals['custom_field_ids'].
        # Use a method to sync after create if needed, or rely on default_get for UI.
        
        return super(AuditMemo, self).create(vals)

    def action_refresh_custom_fields(self):
        """ Syncs the custom fields list with the active Definitions. """
        definitions = self.env['audit.form.definition'].search([('active', '=', True)])
        CustomField = self.env['audit.memo.custom.field']
        
        for memo in self:
            existing_def_ids = memo.custom_field_ids.mapped('definition_id.id')
            
            # Find definitions that are missing for this memo
            missing_defs = definitions.filtered(lambda d: d.id not in existing_def_ids)
            
            new_lines = []
            for definition in missing_defs:
                new_lines.append({
                    'memo_id': memo.id,
                    'definition_id': definition.id,
                })
            
            if new_lines:
                CustomField.create(new_lines)
        
        return True

    def _expand_states(self, states, domain, order=None):
        return [key for key, val in type(self).state.selection]

    # Workflow Actions
    def action_submit_to_partner(self):
        self.ensure_one()
        if not self.engagement_partner_id:
            raise UserError(_("Please select an Engagement Partner."))
        self.state = 'partner_review'

    def action_partner_approve(self):
        self.ensure_one()
        self.state = 'npsg_assignment'

    def action_partner_reject(self):
        self.ensure_one()
        self.state = 'rejected'

    def action_assign_preparer(self):
        self.ensure_one()
        if not self.preparer_id:
            raise UserError(_("Please assign a Preparer."))
        self.state = 'in_progress'

    def action_submit_to_review_1(self):
        self.ensure_one()
        if not self.reviewer_1_id:
            # Prepare can optionally go directly to Final Reviewer if allowed? 
            # Description says: "The preparer can directly send the request to the final reviewer for review."
            pass 
        # But here we assume standard flow or user choice.
        # Let's check logic: if reviewer_1_id is set -> level_1_review, else error or maybe final?
        if self.reviewer_1_id:
            self.state = 'level_1_review'
        else:
             raise UserError(_("Please select a First Level Reviewer or submit to Final Reviewer directly."))

    def action_submit_to_final_review(self):
        self.ensure_one()
        if not self.reviewer_final_id:
             raise UserError(_("Please select a Final Reviewer."))
        self.state = 'final_review'

    def action_review_1_approve(self):
        self.ensure_one()
        # Goes to Final Review
        if not self.reviewer_final_id:
             raise UserError(_("Please select a Final Reviewer."))
        self.state = 'final_review'

    def action_final_approve(self):
        self.ensure_one()
        self.state = 'approved'

    def action_reject(self):
        self.ensure_one()
        # Can go back to previous state or rejected. 
        # Diagram mentions "Back to Preparer" or "Reject". 
        # For simplicity, let's have a method to request changes or reject.
        self.state = 'rejected'

    def action_request_changes(self):
        self.ensure_one()
        # Logic to send back. For now, let's send back to Preparer (In Progress)
        self.state = 'in_progress'

    def action_hold(self):
        self.ensure_one()
        self.state = 'on_hold'

    @api.model
    def _cron_send_pending_reminders(self):
        """ Checks for pending tasks and sends reminders based on configuration. """
        enabled = self.env['ir.config_parameter'].sudo().get_param('audit_tool.reminder_enabled')
        if not enabled:
            return

        frequency = int(self.env['ir.config_parameter'].sudo().get_param('audit_tool.reminder_frequency', 1))
        # Simple Logic: Find tasks pending and not updated in last X days? 
        # Or just ping everyone every X days? 
        # Requirement: "frequency of reminder". Let's assume ping every Frequency Days if not done.
        # We can check write_date.
        
        from datetime import datetime, timedelta
        limit_date = datetime.now() - timedelta(days=frequency)
        
        # Find Memos that are NOT in a terminal state (approved, rejected) 
        # AND haven't been modified recently (to avoid spamming active tasks)
        pending_memos = self.search([
            ('state', 'not in', ['draft', 'approved', 'rejected', 'on_hold']),
            ('write_date', '<=', limit_date)
        ])
        
        for memo in pending_memos:
            user_to_notify = False
            state_label = dict(self._fields['state'].selection).get(memo.state)
            
            if memo.state == 'partner_review':
                user_to_notify = memo.engagement_partner_id
            elif memo.state == 'npsg_assignment':
                user_to_notify = memo.npsg_user_id # Might be empty if unassigned team?
            elif memo.state == 'in_progress':
                user_to_notify = memo.preparer_id
            elif memo.state == 'level_1_review':
                user_to_notify = memo.reviewer_1_id
            elif memo.state == 'final_review':
                user_to_notify = memo.reviewer_final_id
            
            if user_to_notify:
                memo.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user_to_notify.id,
                    summary=f'Reminder: Pending Action - {state_label}',
                    note=f'This memo has been pending your action for more than {frequency} days. Please review.',
                    date_deadline=fields.Date.today()
                )
                # Also log a note so write_date updates? No, activity doesn't always update write_date of record?
                # If we don't update write_date, they will get another reminder next run (if frequency=1).
                # That is probably desired for "Daily Reminders".
                # If they want "Every 3 days", calculating from write_date works.
                pass
