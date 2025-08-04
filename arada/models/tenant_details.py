from odoo import models, fields, api, _
from odoo.exceptions import UserError

class TenantDetails(models.Model):
    _name = 'tenant.details'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tenant Details'

    developement = fields.Char()
    unit_no = fields.Char()
    ground_floor = fields.Char()
    mez_floor = fields.Char()
    outdoor_area_gf = fields.Char()
    outdoor_area_mezz = fields.Char()


    # location
    tenant_name = fields.Char(string="Tenant Name")
    shop_name = fields.Char(string="Proposed Shop Name")
    permitted_use = fields.Char(string="Permitted Use")
    lease_term = fields.Integer(string="Lease Term")

    contact_person = fields.Char(string="Contact Person Name")
    designation = fields.Char(string="Designation")
    company_name = fields.Char(string="Company Name")
    address = fields.Char(string="Address")

    telephone = fields.Char(string="Telephone")
    mobile = fields.Char(string="Mobile")
    fax = fields.Char(string="Fax")
    email = fields.Char(string="Email")


    # ---
    fit_out_commencement_date = fields.Date(string="Fit out commencement date")
    concept_drawing_submission_date = fields.Date(string="Concept drawing submission date")
    fit_out_period = fields.Integer(string="Fit-out period")
    detail_drawing_submission_date = fields.Date(string="Detail design drawing submission date")
    opening_date = fields.Date(string="Opening date")
    notes = fields.Text(string="Notes")
    lop = fields.Integer(string="LOP")

    # ----
    special_requirements = fields.Text()

    # ---
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'tenant_details_ir_attachments_rel',  # Relation table
        'tenant_id',                          # Your model's FK column
        'attachment_id',                      # Attachment model's FK
        string="Attachments",
        domain=[('type', '=', 'binary')],
    )

    is_ptl = fields.Boolean()

    def action_approve_ptl(self):
        pass

    def action_reject_ptl(self):
        pass
    