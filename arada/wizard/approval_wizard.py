from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime



class PTLApprovalWizard(models.TransientModel):
    _name = 'ptl.approval.wizard'
    _description = 'PTL Approval/Rejection Wizard'

    ptl_form_id = fields.Many2one('ptl.form', string='PTL Form', required=True)
    section_name = fields.Char(string='Section Name', required=True)
    action_type = fields.Selection([
        ('approve', 'Approve'),
        ('reject', 'Reject')
    ], string='Action Type', required=True)
    comments = fields.Text(string='Comments', required=True)

    def action_confirm(self):
        self.ensure_one()
        
        # Map section names to field names
        section_field_map = {
            'PTL Section': 'ptl_section_status',
            'Critical Path Section': 'critical_path_section_status',
            'Tenant Appointment Section': 'tenant_appointment_section_status',
            'Conceptual Design Section': 'conceptual_design_section_status',
        }
        
        field_name = section_field_map.get(self.section_name)
        print("field name - ", field_name)
        if field_name:
            new_status = 'approved' if self.action_type == 'approve' else 'rejected'
            self.ptl_form_id.write({field_name: new_status})

            if self.ptl_form_id.ptl_section_status == 'approved':
                self.ptl_form_id.global_status = 'form_verification'

            # if self.ptl_form_id.critical_path_section_status == 'approved':
            #     print("ifc conditoin - ", self.ptl_form_id.critical_path_section_status)
            #     self.ptl_form_id.global_status = 'kick_off_meeting'


            # Log the action in chatter
            # message = f"{self.section_name} {self.action_type}d with comments: {self.comments}"
            # self.ptl_form_id.message_post(body=message, message_type='comment')
        
        return {'type': 'ir.actions.act_window_close'} 
