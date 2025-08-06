from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

class TenantDetails(models.Model):
    _name = 'tenant.details'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tenant Details'

    approval_state = fields.Selection([
        ('ptl','PTL'),
        ('cp','Critical Path'),
        ('ta','Tenant Appointment'),
        ('cd','Conceptual Design'),
        ('ad','Arch Design'),
        ('md','MEP Design'),
        ('sa','Sample Approval'),
        ('pm','Pre Mob'),
    ], string="Approval for", default="ptl")
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

    # Workflow Status
    workflow_state = fields.Selection([
        ('new', 'New'),
        ('pending_rdd', 'Pending RDD'),
        ('pending_tenant_contractor', 'Pending Tenant / Contractor'),
        ('pending_mep', 'Pending MEP'),
        ('pending_sample_approval', 'Pending Sample Approval'),
        ('pending_pre_mob', 'Pending Pre-mobilization'),
        ('pending_noc', 'Pending NOC'),
        ('pending_inspection', 'Pending Inspection'),
        ('completed', 'Completed')
    ], string='Workflow Status', default='new', tracking=True)

    # Critical Path Fields - Design Phase
    kickoff_meeting_days = fields.Integer(string='Kick-Off meeting / Project handover Days', default=0)
    kickoff_meeting_date = fields.Date(string='Kick-Off meeting / Project handover Date')
    
    concept_design_days = fields.Integer(string='Concept design submission Days', default=0)
    concept_design_date = fields.Date(string='Concept design submission Date')
    
    arch_detailed_design_days = fields.Integer(string='Arch detailed design submission Days', default=0)
    arch_detailed_design_date = fields.Date(string='Arch detailed design submission Date')
    
    mep_design_days = fields.Integer(string='MEP design submission Days', default=0)
    mep_design_date = fields.Date(string='MEP design submission Date')
    
    # Critical Path Fields - Authority Phase
    civil_defence_days = fields.Integer(string='Civil defence approval Days', default=0)
    civil_defence_date = fields.Date(string='Civil defence approval Date')
    
    municipality_fitout_days = fields.Integer(string='Municipality fit-out permit/Authority submissions Days', default=0)
    municipality_fitout_date = fields.Date(string='Municipality fit-out permit/Authority submissions Date')
    
    sewa_approval_days = fields.Integer(string='SEWA / Water & power approval Days', default=0)
    sewa_approval_date = fields.Date(string='SEWA / Water & power approval Date')
    
    # Critical Path Fields - Execution Phase
    site_mobilization_days = fields.Integer(string='Site mobilization Days', default=0)
    site_mobilization_date = fields.Date(string='Site mobilization Date')
    
    fitout_works_days = fields.Integer(string='Fitout works Days', default=0)
    fitout_works_date = fields.Date(string='Fitout works Date')
    
    final_inspection_days = fields.Integer(string='Final inspection Days', default=0)
    final_inspection_date = fields.Date(string='Final inspection Date')
    
    snag_completion_days = fields.Integer(string='Snag completion Days', default=0)
    snag_completion_date = fields.Date(string='Snag completion Date')
    
    handover_approvals_days = fields.Integer(string='Handover of all approvals Days', default=0)
    handover_approvals_date = fields.Date(string='Handover of all approvals Date')
    
    merchandising_start_days = fields.Integer(string='Merchandising start Days', default=0)
    merchandising_start_date = fields.Date(string='Merchandising start Date')
    
    trade_date_days = fields.Integer(string='Trade date Days', default=0)
    trade_date_date = fields.Date(string='Trade date Date')
    
    # Critical Path Additional Fields
    lop_penalty = fields.Float(string='Late opening penalty (LOP) AED per calendar day', default=0.0)
    critical_path_comments = fields.Text(string='Critical Path Comments')
    
    # Computed fields for progress tracking
    total_days = fields.Integer(string='Total Days', compute='_compute_total_days', store=True)
    completed_tasks = fields.Integer(string='Completed Tasks', compute='_compute_completed_tasks', store=True)
    progress_percentage = fields.Float(string='Progress Percentage', compute='_compute_progress_percentage', store=True)
    
    # Tenant Appointment Fields - Primary Contact
    primary_contact_name = fields.Char(string='Primary Contact Name')
    primary_contact_designation = fields.Char(string='Primary Contact Designation')
    primary_contact_company = fields.Char(string='Primary Contact Company')
    primary_contact_telephone = fields.Char(string='Primary Contact Telephone', default='+971 55 223 3444')
    primary_contact_mobile = fields.Char(string='Primary Contact Mobile', default='+971 55 223 3444')
    primary_contact_email = fields.Char(string='Primary Contact Email')
    primary_contact_experience = fields.Text(string='Primary Contact Experience', default='Experience goes here...')
    
    # Tenant Appointment Fields - Secondary Contact
    secondary_contact_name = fields.Char(string='Secondary Contact Name')
    secondary_contact_designation = fields.Char(string='Secondary Contact Designation')
    secondary_contact_company = fields.Char(string='Secondary Contact Company')
    secondary_contact_telephone = fields.Char(string='Secondary Contact Telephone', default='+971 55 223 3444')
    secondary_contact_mobile = fields.Char(string='Secondary Contact Mobile', default='+971 55 223 3444')
    secondary_contact_email = fields.Char(string='Secondary Contact Email')
    secondary_contact_experience = fields.Text(string='Secondary Contact Experience', default='Experience goes here...')
    
    # Tenant Appointment Fields - Tenant Designer
    tenant_designer_name = fields.Char(string='Tenant Designer Name')
    tenant_designer_company = fields.Char(string='Tenant Designer Company')
    tenant_designer_contact = fields.Char(string='Tenant Designer Contact Number', default='+971 55 223 3444')
    tenant_designer_email = fields.Char(string='Tenant Designer Email')
    tenant_designer_work_history = fields.Text(string='Tenant Designer Work History', default='Work history goes here...')
    
    # Tenant Appointment Fields - Tenant Contractor
    tenant_contractor_name = fields.Char(string='Tenant Contractor Name')
    tenant_contractor_company = fields.Char(string='Tenant Contractor Company Name')
    tenant_contractor_contact = fields.Char(string='Tenant Contractor Contact Number', default='+971 55 223 3444')
    tenant_contractor_email = fields.Char(string='Tenant Contractor Email')
    tenant_contractor_work_history = fields.Text(string='Tenant Contractor Work History', default='Work history goes here...')
    tenant_contractor_trade_license = fields.Binary(string='Tenant Contractor Trade License')
    tenant_contractor_company_profile = fields.Binary(string='Tenant Contractor Company Profile')
    tenant_contractor_comments = fields.Text(string='Tenant Contractor Comments', default='Comments received')
    
    # Tenant Appointment Status and Attachments
    tenant_appointment_status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Overall Status', default='no_objection', tracking=True)
    
    tenant_appointment_attachments = fields.Many2many(
        'ir.attachment',
        'tenant_appointment_ir_attachments_rel',
        'tenant_appointment_id',
        'attachment_id',
        string="Tenant Appointment Attachments",
        domain=[('type', '=', 'binary')],
    )
    
    tenant_appointment_comments = fields.Text(string='Tenant Appointment Comments')
    
    # Conceptual Design Fields - Standard Format Required
    concept_drawings_pdf_attachment = fields.Binary(string='1 set of all drawings - softcopy in PDF format')
    concept_drawings_pdf_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Drawings PDF Status', default='no_objection')
    
    tvr_form_attachment = fields.Binary(string='Tenant Variation Request (TVR - Form 09)')
    tvr_form_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='TVR Form Status', default='no_objection')
    
    # Conceptual Design Fields - Documents Required
    furniture_layout_attachment = fields.Binary(string='Furniture layout plan - with merchandising and services')
    furniture_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Furniture Layout Status', default='no_objection')
    
    shop_front_3d_attachment = fields.Binary(string='Shop front - with signage - 3D Image - in colour')
    shop_front_3d_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Shop Front 3D Status', default='no_objection')
    
    shop_front_elevation_attachment = fields.Binary(string='Shop front Elevation - with SIGNAGE')
    shop_front_elevation_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Shop Front Elevation Status', default='no_objection')
    
    interior_3d_attachment = fields.Binary(string='3D image in colored - interior*')
    interior_3d_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Interior 3D Status', default='no_objection')
    
    previous_shops_photos_attachment = fields.Binary(string='Photos of previous shops or anything that helps explain the concept')
    previous_shops_photos_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Previous Shops Photos Status', default='no_objection')
    
    # Conceptual Design Overall Status and Attachments
    conceptual_design_status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Conceptual Design Overall Status', default='no_objection', tracking=True)
    
    conceptual_design_attachments = fields.Many2many(
        'ir.attachment',
        'conceptual_design_ir_attachments_rel',
        'conceptual_design_id',
        'attachment_id',
        string="Conceptual Design Attachments",
        domain=[('type', '=', 'binary')],
    )
    
    conceptual_design_comments = fields.Text(string='Conceptual Design Comments')
    
    # Arch Design Fields - Standard Required
    arch_drawings_pdf_attachment = fields.Binary(string='1 set of all drawings - softcopy in PDF format*')
    arch_drawings_pdf_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Arch Drawings PDF Status', default='no_objection')
    
    arch_tvr_form_attachment = fields.Binary(string='Tenant variation request (TVR - Form 09)')
    arch_tvr_form_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Arch TVR Form Status', default='no_objection')
    
    materials_referenced_attachment = fields.Binary(string='Materials are clearly referenced on drawings')
    materials_referenced_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Materials Referenced Status', default='no_objection')
    
    sample_board_attachment = fields.Binary(string='Sample board doesn\'t exceed 50cm X 35cm (use more than 1 if required)')
    sample_board_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Sample Board Status', default='no_objection')
    
    material_samples_attachment = fields.Binary(string='Actual material samples to be included - submit 1 set (to keep 1 sample at site)')
    material_samples_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Material Samples Status', default='no_objection')
    
    # Arch Design Fields - Checklist of Documents Required
    arch_furniture_layout_attachment = fields.Binary(string='Furniture layout plan-with merchandising and services (DB&FAP)*')
    arch_furniture_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Arch Furniture Layout Status', default='no_objection')
    
    flooring_plan_attachment = fields.Binary(string='Flooring plan*')
    flooring_plan_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Flooring Plan Status', default='no_objection')
    
    ceiling_plan_attachment = fields.Binary(string='Reflected ceiling plan with lighting, AC diffusers, smoke detectors, sprinklers, speakers*')
    ceiling_plan_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Ceiling Plan Status', default='no_objection')
    
    interior_elevations_attachment = fields.Binary(string='Interior section elevations (all)')
    interior_elevations_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Interior Elevations Status', default='no_objection')
    
    shop_front_workshop_attachment = fields.Binary(string='Shop front workshop drawings - Including SIGNAGE installation details & interface details with landlord finishes*')
    shop_front_workshop_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Shop Front Workshop Status', default='no_objection')
    
    signage_package_attachment = fields.Binary(string='Signage package (interior, shop front & exterior) - including package for submittal to statutory Authorities for approval')
    signage_package_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Signage Package Status', default='no_objection')
    
    shop_front_sections_attachment = fields.Binary(string='Shop front sections (at least 1 through entrance and 1 through window display)*')
    shop_front_sections_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Shop Front Sections Status', default='no_objection')
    
    updated_shopfront_3d_attachment = fields.Binary(string='Updated shopfront - 3D images in color')
    updated_shopfront_3d_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Updated Shopfront 3D Status', default='no_objection')
    
    material_finishes_schedule_attachment = fields.Binary(string='Schedule of material finishes as referenced on the drawings*, Structural calculation for special requirements, Glazing, Heavy equipment, Safe, etc.*')
    material_finishes_schedule_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Material Finishes Schedule Status', default='no_objection')
    
    updated_interior_3d_attachment = fields.Binary(string='Updated interior 3D images')
    updated_interior_3d_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Updated Interior 3D Status', default='no_objection')
    
    # Arch Design Overall Status and Attachments
    arch_design_status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Arch Design Overall Status', default='no_objection', tracking=True)
    
    arch_design_attachments = fields.Many2many(
        'ir.attachment',
        'arch_design_ir_attachments_rel',
        'arch_design_id',
        'attachment_id',
        string="Arch Design Attachments",
        domain=[('type', '=', 'binary')],
    )
    
    arch_design_comments = fields.Text(string='Arch Design Comments')
    
    # MEP Design Fields - Common drawings required for all units
    reflected_ceiling_plan_attachment = fields.Binary(string='Reflected Ceiling Plan')
    reflected_ceiling_plan_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    lighting_layout_attachment = fields.Binary(string='Lighting Layout')
    lighting_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    power_layout_attachment = fields.Binary(string='Power Layout')
    power_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    load_schedule_attachment = fields.Binary(string='Load Schedule/ Single Line Drawings')
    load_schedule_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    telephone_data_layout_attachment = fields.Binary(string='Telephone/ Data Layout')
    telephone_data_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    fire_alarm_layout_attachment = fields.Binary(string='Fire Alarm Layout (Above and Below ceiling) and Schematic')
    fire_alarm_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    emergency_light_layout_attachment = fields.Binary(string='Emergency Light Layout')
    emergency_light_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    hvac_layout_attachment = fields.Binary(string='HVAC Layout')
    hvac_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    refrigerant_piping_layout_attachment = fields.Binary(string='Refrigerant Piping Layout')
    refrigerant_piping_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    heat_load_calculation_attachment = fields.Binary(string='Heat Load Calculation')
    heat_load_calculation_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    ac_equipment_data_sheet_attachment = fields.Binary(string='AC Equipment Data Sheet')
    ac_equipment_data_sheet_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    fahu_data_sheet_attachment = fields.Binary(string='FAHU Data Sheet')
    fahu_data_sheet_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    ecology_unit_data_sheet_attachment = fields.Binary(string='Ecology Unit Data Sheet')
    ecology_unit_data_sheet_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    kitchen_hood_data_sheet_attachment = fields.Binary(string='Kitchen Hood Data Sheet and Layout')
    kitchen_hood_data_sheet_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    ventilation_calculation_attachment = fields.Binary(string='Ventilation calculation/ Schematic')
    ventilation_calculation_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    kitchen_extract_layout_attachment = fields.Binary(string='Kitchen Extract Layout')
    kitchen_extract_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    fresh_air_layout_attachment = fields.Binary(string='Fresh Air Layout')
    fresh_air_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    general_ventilation_layout_attachment = fields.Binary(string='General Ventilation Layout')
    general_ventilation_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    condensate_drain_layout_attachment = fields.Binary(string='Condensate Drain Layout')
    condensate_drain_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    firefighting_layout_attachment = fields.Binary(string='Firefighting Layout')
    firefighting_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    water_supply_layout_attachment = fields.Binary(string='Water Supply Layout')
    water_supply_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    drainage_layout_attachment = fields.Binary(string='Drainage Layout')
    drainage_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    grease_trap_data_sheet_attachment = fields.Binary(string='Grease Trap Data Sheet')
    grease_trap_data_sheet_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    natural_gas_layout_attachment = fields.Binary(string='Natural Gas Layout')
    natural_gas_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    fire_suppression_layout_attachment = fields.Binary(string='Fire Suppression Layout')
    fire_suppression_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    kitchen_equipment_layout_attachment = fields.Binary(string='Kitchen Equipment Layout')
    kitchen_equipment_layout_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    smoke_extract_system_attachment = fields.Binary(string='Smoke Extract System')
    smoke_extract_system_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    vendor_list_compliance_attachment = fields.Binary(string='Vendor List Compliance')
    vendor_list_compliance_status = fields.Selection([
        ('pending', 'Pending'),
        ('awaiting', 'Awaiting'),
        ('no_objection', 'No objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    # Filename fields for MEP attachments
    reflected_ceiling_plan_filename = fields.Char()
    lighting_layout_filename = fields.Char()
    power_layout_filename = fields.Char()
    load_schedule_filename = fields.Char()
    telephone_data_layout_filename = fields.Char()
    fire_alarm_layout_filename = fields.Char()
    emergency_light_layout_filename = fields.Char()
    hvac_layout_filename = fields.Char()
    refrigerant_piping_layout_filename = fields.Char()
    heat_load_calculation_filename = fields.Char()
    ac_equipment_data_sheet_filename = fields.Char()
    fahu_data_sheet_filename = fields.Char()
    ecology_unit_data_sheet_filename = fields.Char()
    kitchen_hood_data_sheet_filename = fields.Char()
    ventilation_calculation_filename = fields.Char()
    kitchen_extract_layout_filename = fields.Char()
    fresh_air_layout_filename = fields.Char()
    general_ventilation_layout_filename = fields.Char()
    condensate_drain_layout_filename = fields.Char()
    firefighting_layout_filename = fields.Char()
    water_supply_layout_filename = fields.Char()
    drainage_layout_filename = fields.Char()
    grease_trap_data_sheet_filename = fields.Char()
    natural_gas_layout_filename = fields.Char()
    fire_suppression_layout_filename = fields.Char()
    kitchen_equipment_layout_filename = fields.Char()
    smoke_extract_system_filename = fields.Char()
    vendor_list_compliance_filename = fields.Char()
    
    mep_conditions = fields.Text(string='MEP Conditions', readonly=True, default='1. All changes on revised submission to be highlighted.')

    # Sample Approval Fields - RDD
    rdd_sample_description = fields.Text(string='Sample Description', help='Description for RDD sample approval')
    rdd_sample_attachment = fields.Binary(string='Attach', filename='rdd_sample_filename')
    rdd_sample_filename = fields.Char()
    rdd_sample_status = fields.Selection([
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('no_objection_comments', 'No Objection with comments'),
        ('objection', 'Objection'),
        ('revise_resubmit', 'Revise & Resubmit')
    ], string='Status', default='pending', tracking=True)
    rdd_sample_comments = fields.Text(string='Comments', help='Comments for RDD sample approval')
    
    # Sample Approval Fields - MEP
    mep_sample_description = fields.Text(string='Sample Description', help='Description for MEP sample approval')
    mep_sample_attachment = fields.Binary(string='Attach', filename='mep_sample_filename')
    mep_sample_filename = fields.Char()
    mep_sample_status = fields.Selection([
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('no_objection_comments', 'No Objection with comments'),
        ('objection', 'Objection'),
        ('revise_resubmit', 'Revise & Resubmit')
    ], string='Status', default='pending', tracking=True)
    mep_sample_comments = fields.Text(string='Comments', help='Comments for MEP sample approval')

    # Pre-mobilization Requirements Fields
    design_approval_attachment = fields.Binary(string='Design Approval*', filename='design_approval_filename')
    design_approval_filename = fields.Char()
    design_approval_comments = fields.Text(string='Comments')
    design_approval_status = fields.Selection([
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('objection', 'Objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    contractors_insurance_attachment = fields.Binary(string="Contractor's All Risks Insurance with TPL and Workmen's Compensation Certificate Copy*", filename='contractors_insurance_filename')
    contractors_insurance_filename = fields.Char()
    contractors_insurance_comments = fields.Text(string='Comments')
    contractors_insurance_status = fields.Selection([
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('objection', 'Objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    fitout_method_statement_attachment = fields.Binary(string="Fit-out Work Method Statement and Risks Assessment - MSRA (full scope)*", filename='fitout_method_statement_filename')
    fitout_method_statement_filename = fields.Char()
    fitout_method_statement_comments = fields.Text(string='Comments')
    fitout_method_statement_status = fields.Selection([
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('objection', 'Objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    hse_induction_certificate_attachment = fields.Binary(string='HSE Safety Induction Certificate', filename='hse_induction_certificate_filename')
    hse_induction_certificate_filename = fields.Char()
    hse_induction_certificate_comments = fields.Text(string='Comments')
    hse_induction_certificate_status = fields.Selection([
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('objection', 'Objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    contractors_hse_plan_attachment = fields.Binary(string="Contractor's HSE Plan*", filename='contractors_hse_plan_filename')
    contractors_hse_plan_filename = fields.Char()
    contractors_hse_plan_comments = fields.Text(string='Comments')
    contractors_hse_plan_status = fields.Selection([
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('objection', 'Objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    hse_certified_personnel_attachment = fields.Binary(string="HSE Certified Personnel's Valid ID or Certificate", filename='hse_certified_personnel_filename')
    hse_certified_personnel_filename = fields.Char()
    hse_certified_personnel_comments = fields.Text(string='Comments')
    hse_certified_personnel_status = fields.Selection([
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('objection', 'Objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    program_of_works_attachment = fields.Binary(string='Program of Works*', filename='program_of_works_filename')
    program_of_works_filename = fields.Char()
    program_of_works_comments = fields.Text(string='Comments')
    program_of_works_status = fields.Selection([
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('objection', 'Objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    temporary_power_water_attachment = fields.Binary(string="Temporary power and water for fit-out use (to advise applicable fees, if any. Tenant contractor should install sub-meter which will be verified by Arada Care/FM)", filename='temporary_power_water_filename')
    temporary_power_water_filename = fields.Char()
    temporary_power_water_comments = fields.Text(string='Comments')
    temporary_power_water_status = fields.Selection([
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('objection', 'Objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    landlords_work_permit_attachment = fields.Binary(string="Landlord's Work Permit Application (Fit-out Work Permit and Hot-work)*", filename='landlords_work_permit_filename')
    landlords_work_permit_filename = fields.Char()
    landlords_work_permit_comments = fields.Text(string='Comments')
    landlords_work_permit_status = fields.Selection([
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('objection', 'Objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    municipality_approved_drawings_attachment = fields.Binary(string="Municipality/Civil Defence Approved Drawings (Submission Reference No./ Proof of Application to provide for preliminary works to proceed)", filename='municipality_approved_drawings_filename')
    municipality_approved_drawings_filename = fields.Char()
    municipality_approved_drawings_comments = fields.Text(string='Comments')
    municipality_approved_drawings_status = fields.Selection([
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('objection', 'Objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)
    
    others_attachment = fields.Binary(string='Others', filename='others_filename')
    others_filename = fields.Char()
    others_comments = fields.Text(string='Comments')
    others_status = fields.Selection([
        ('pending', 'Pending'),
        ('no_objection', 'No Objection'),
        ('objection', 'Objection'),
        ('revise_resubmit', 'Revise & Resubmit'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='pending', tracking=True)

    # NOC Tab Fields
    noc_attention_person = fields.Char(string="Attention", default="Aljada Mall Project Manager")
    noc_tenant_main_contractor = fields.Char(string="Tenant Main contractor")
    noc_arada_main_contractor = fields.Char(string="Arada Main contractor")
    noc_development = fields.Char(string="Development", default="Aljada")

    # Computed fields for NOC display section
    noc_unit_number_display = fields.Char(string="Unit Number", compute='_compute_noc_details', store=True)
    noc_tenant_name_display = fields.Char(string="Tenant Name", compute='_compute_noc_details', store=True)
    noc_unit_name_display = fields.Char(string="Unit name", compute='_compute_noc_details', store=True)
    noc_designation_display = fields.Char(string="Designation", default="Design")
    noc_company_name_display = fields.Char(string="Company", default="Company name")
    noc_mobile_number_display = fields.Char(string="Mobile Number", default="+971 50 222 3333")
    noc_telephone_display = fields.Char(string="Telephone", default="+971 60 000 000")
    noc_email_address_display = fields.Char(string="Email Address", default="company@gmail.com")
    noc_attention_display = fields.Char(string="Attention", compute='_compute_noc_details', store=True)
    noc_subject_display = fields.Char(string="Subject", default="No Objection for Site Mobilization")

    # Inspection Tab Fields
    inspection_water_proofing = fields.Boolean(string='Water proofing of witnessing')
    inspection_water_proofing_date = fields.Date(string='Water Proofing Date')
    
    inspection_gravity_test = fields.Boolean(string='Gravity test inspection for drainage piping installation')
    inspection_gravity_test_date = fields.Date(string='Gravity Test Date')
    
    inspection_kitchen_tiles = fields.Boolean(string='Kitchen tiles & grout installation inspection')
    inspection_kitchen_tiles_date = fields.Date(string='Kitchen Tiles Date')
    
    inspection_pre_ceiling = fields.Boolean(string='Pre-Ceiling closure inspection')
    inspection_pre_ceiling_date = fields.Date(string='Pre-Ceiling Date')
    
    inspection_sprinkler_pipe = fields.Boolean(string='Sprinkler pipe pressure test inspection')
    inspection_sprinkler_pipe_date = fields.Date(string='Sprinkler Pipe Date')
    
    inspection_fire_alarm = fields.Boolean(string='Fire alarm continuity test')
    inspection_fire_alarm_date = fields.Date(string='Fire Alarm Date')
    
    inspection_chilled_water = fields.Boolean(string='Chilled water/ Refrigerant pipe pressure test inspection')
    inspection_chilled_water_date = fields.Date(string='Chilled Water Date')
    
    inspection_water_pipe = fields.Boolean(string='Water pipe pressure test inspection')
    inspection_water_pipe_date = fields.Date(string='Water Pipe Date')
    
    inspection_db_megger = fields.Boolean(string='DB / Megger test inspection')
    inspection_db_megger_date = fields.Date(string='DB/Megger Test Date')
    
    inspection_general_flooring = fields.Boolean(string='General flooring inspection (Landlord FCO/Manhole)')
    inspection_general_flooring_date = fields.Date(string='General Flooring Date')
    
    inspection_grease_trap = fields.Boolean(string='Grease Trap installation')
    inspection_grease_trap_date = fields.Date(string='Grease Trap Date')
    
    inspection_fcu_ahu = fields.Boolean(string='FCU / AHU / Extract fan installation')
    inspection_fcu_ahu_date = fields.Date(string='FCU/AHU Date')
    
    inspection_roof = fields.Boolean(string='Roof inspection')
    inspection_roof_date = fields.Date(string='Roof Inspection Date')
    
    inspection_final_pre_opening = fields.Boolean(string='Final Pre-Opening Inspection')
    inspection_final_pre_opening_date = fields.Date(string='Final Pre-Opening Date')
    
    inspection_others = fields.Boolean(string='Others')
    inspection_others_date = fields.Date(string='Others Date')
    
    # Attachment and Comments
    inspection_attachment = fields.Binary(string='Attachment')
    inspection_attachment_filename = fields.Char()
    inspection_comments = fields.Text(string='Inspection Comments')

    # Workflow related fields
    workflow_instance_id = fields.Many2one('arada.workflow.instance', string='Workflow Instance', tracking=True)
    current_workflow_state = fields.Many2one('arada.workflow.state', string='Current Workflow State', tracking=True)
    available_workflow_actions = fields.Many2many('arada.workflow.action', compute='_compute_available_workflow_actions', string='Available Actions')

    @api.depends('workflow_instance_id', 'current_workflow_state')
    def _compute_available_workflow_actions(self):
        for record in self:
            if record.workflow_instance_id:
                record.available_workflow_actions = record.workflow_instance_id.available_action_ids
            else:
                record.available_workflow_actions = False

    def action_start_workflow(self):
        """Start a workflow for this tenant"""
        self.ensure_one()
        
        # Create workflow instance
        workflow = self.env['arada.workflow'].search([('workflow_type', '=', 'tenant_approval')], limit=1)
        if not workflow:
            raise UserError(_('No tenant approval workflow found.'))
        
        instance = self.env['arada.workflow.instance'].create({
            'name': f'Workflow for {self.tenant_name}',
            'workflow_id': workflow.id,
            'tenant_details_id': self.id
        })
        
        self.workflow_instance_id = instance.id
        self.current_workflow_state = instance.current_state_id
        
        return True

    def action_execute_workflow_action(self, action_id):
        """Execute a workflow action"""
        self.ensure_one()
        
        if not self.workflow_instance_id:
            raise UserError(_('No workflow instance found.'))
        
        self.workflow_instance_id.action_execute_transition(action_id)
        self.current_workflow_state = self.workflow_instance_id.current_state_id
        
        return True

    @api.depends('unit_no', 'tenant_name', 'shop_name', 'noc_attention_person')
    def _compute_noc_details(self):
        for record in self:
            record.noc_unit_number_display = record.unit_no or "[Unit number]"
            record.noc_tenant_name_display = record.tenant_name or "[Al Bahar Al Mutawasit Rest LLC]"
            record.noc_unit_name_display = record.shop_name or "[Aljada]"
            record.noc_attention_display = record.noc_attention_person or "[Aljada Mall Project Manager]"

    @api.depends('kickoff_meeting_days', 'concept_design_days', 'arch_detailed_design_days', 'mep_design_days',
                 'civil_defence_days', 'municipality_fitout_days', 'sewa_approval_days',
                 'site_mobilization_days', 'fitout_works_days', 'final_inspection_days',
                 'snag_completion_days', 'handover_approvals_days', 'merchandising_start_days', 'trade_date_days')
    def _compute_total_days(self):
        for record in self:
            record.total_days = (record.kickoff_meeting_days + record.concept_design_days + 
                               record.arch_detailed_design_days + record.mep_design_days +
                               record.civil_defence_days + record.municipality_fitout_days + 
                               record.sewa_approval_days + record.site_mobilization_days +
                               record.fitout_works_days + record.final_inspection_days +
                               record.snag_completion_days + record.handover_approvals_days +
                               record.merchandising_start_days + record.trade_date_days)
    
    @api.depends('kickoff_meeting_date', 'concept_design_date', 'arch_detailed_design_date', 'mep_design_date',
                 'civil_defence_date', 'municipality_fitout_date', 'sewa_approval_date',
                 'site_mobilization_date', 'fitout_works_date', 'final_inspection_date',
                 'snag_completion_date', 'handover_approvals_date', 'merchandising_start_date', 'trade_date_date')
    def _compute_completed_tasks(self):
        for record in self:
            completed = 0
            date_fields = ['kickoff_meeting_date', 'concept_design_date', 'arch_detailed_design_date', 
                          'mep_design_date', 'civil_defence_date', 'municipality_fitout_date', 
                          'sewa_approval_date', 'site_mobilization_date', 'fitout_works_date', 
                          'final_inspection_date', 'snag_completion_date', 'handover_approvals_date', 
                          'merchandising_start_date', 'trade_date_date']
            
            for field in date_fields:
                if getattr(record, field):
                    completed += 1
            record.completed_tasks = completed
    
    @api.depends('completed_tasks', 'total_days')
    def _compute_progress_percentage(self):
        for record in self:
            if record.total_days > 0:
                record.progress_percentage = (record.completed_tasks / 14) * 100  # 14 total tasks
            else:
                record.progress_percentage = 0.0

    def action_approve_ptl(self):
        pass

    def action_reject_ptl(self):
        pass
    
    def action_send_tenant_appointment(self):
        """Send tenant appointment for approval"""
        self.tenant_appointment_status = 'pending'
        return True
    
    def action_send_conceptual_design(self):
        """Send conceptual design for approval"""
        self.conceptual_design_status = 'pending'
        return True
    
    def action_send_arch_design(self):
        """Send arch design for approval"""
        self.arch_design_status = 'pending'
        return True
    
    # Workflow Actions
    def action_move_to_pending_rdd(self):
        """Move to Pending RDD"""
        self.workflow_state = 'pending_rdd'
        return True
    
    def action_move_to_pending_tenant_contractor(self):
        """Move to Pending Tenant / Contractor"""
        self.workflow_state = 'pending_tenant_contractor'
        return True
    
    def action_move_to_pending_mep(self):
        """Move to Pending MEP"""
        self.workflow_state = 'pending_mep'
        return True
    
    def action_complete_workflow(self):
        """Complete workflow"""
        self.workflow_state = 'completed'
        return True 