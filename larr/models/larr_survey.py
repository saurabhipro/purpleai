from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging
import uuid

_logger = logging.getLogger(__name__)


class LARRSurvey(models.Model):
    _name = 'larr.survey'
    _description = 'LARR Survey Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Survey ID', copy=False, readonly=True, 
                      default=lambda self: str(uuid.uuid4()))
    
    # Survey Details
    survey_no = fields.Char('Survey No.', tracking=True)
    survey_date = fields.Date('Survey Date', tracking=True, default=fields.Date.today)
    project_id = fields.Many2one('larr.project', 'Project', tracking=True)
    package_id = fields.Many2one('larr.package', 'Package', tracking=True)
    sub_package_id = fields.Many2one('larr.sub.package', 'Sub Package', tracking=True)
    village_id = fields.Many2one('larr.village', 'Village', tracking=True)
    district_id = fields.Many2one('larr.district', 'District', related='village_id.district_id', store=True, tracking=True)
    
    survey_type = fields.Selection([
        ('physical', 'Physical'),
        ('digital', 'Digital'),
        ('hybrid', 'Hybrid')
    ], default='physical', tracking=True)
    
    survey_status = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)
    
    survey_officer = fields.Char('Survey Officer', tracking=True)
    surveyor_id = fields.Many2one('hr.employee', 'Surveyor', tracking=True)
    
    # Khasra Details
    khasra_no = fields.Char('Khasra No.', tracking=True)
    khatauni_no = fields.Char('Khatauni No.', tracking=True)
    land_area = fields.Float('Land Area (Ha)', tracking=True)
    land_type = fields.Selection([
        ('agricultural', 'कृषि (Agriculture)'),
        ('residential', 'आवासीय (Residential)'),
        ('commercial', 'वाणिज्यिक (Commercial)'),
        ('industrial', 'औद्योगिक (Industrial)'),
        ('mixed', 'मिश्रित (Mixed)'),
        ('forest', 'वन (Forest)'),
        ('wasteland', 'बंजर भूमि (Wasteland)'),
        ('other', 'अन्य (Other)')
    ], tracking=True)
    
    land_class = fields.Selection([
        ('category_1', 'श्रेणी-1 (Category-1)'),
        ('category_2', 'श्रेणी-2 (Category-2)'),
        ('category_3', 'श्रेणी-3 (Category-3)'),
        ('category_4', 'श्रेणी-4 (Category-4)')
    ], tracking=True)
    
    # Owner Details
    owner_ids = fields.One2many('larr.owner', 'survey_id', string='Owners')
    owner_count = fields.Integer(compute='_compute_owner_count', string='Owner Count')
    main_owner_id = fields.Many2one('larr.owner', compute='_compute_main_owner', string='Main Owner', store=True)
    
    # Legacy fields for backward compatibility
    owner_name = fields.Char('Owner Name', tracking=True)
    owner_contact = fields.Char('Owner Contact', tracking=True)
    owner_address = fields.Text('Owner Address', tracking=True)
    owner_status = fields.Selection([
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('in_progress', 'In Progress')
    ], default='pending', tracking=True)
    
    current_stage = fields.Selection([
        ('lao', 'LAO'),
        ('commissioner', 'Commissioner'),
        ('case_worker', 'Case Worker'),
        ('surveyor', 'Surveyor'),
        ('completed', 'Completed')
    ], default='surveyor', tracking=True)
    
    @api.depends('owner_ids')
    def _compute_owner_count(self):
        for record in self:
            record.owner_count = len(record.owner_ids)
    
    @api.depends('owner_ids', 'owner_ids.is_main_owner')
    def _compute_main_owner(self):
        for record in self:
            main_owner = record.owner_ids.filtered(lambda o: o.is_main_owner)
            record.main_owner_id = main_owner[0] if main_owner else False
    
    # Land Details
    total_extent_k = fields.Float('Total Extent (K)', tracking=True)
    total_extent_m = fields.Float('Total Extent (M)', tracking=True)
    khasra_k = fields.Float('Khasra (K)', tracking=True)
    khasra_m = fields.Float('Khasra (M)', tracking=True)
    remaining_k = fields.Float('Remaining (K)', tracking=True)
    remaining_m = fields.Float('Remaining (M)', tracking=True)
    
    assessment_rs = fields.Float('Assessment (Rs)', tracking=True)
    assessment_paisa = fields.Float('Assessment (Paisa)', tracking=True)
    
    current_land_use = fields.Selection([
        ('agricultural', 'Agricultural'),
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('industrial', 'Industrial'),
        ('mixed', 'Mixed'),
        ('fallow', 'Fallow'),
        ('other', 'Other')
    ], tracking=True)
    
    land_grade = fields.Selection([
        ('grade_a', 'Grade A'),
        ('grade_b', 'Grade B'),
        ('grade_c', 'Grade C'),
        ('grade_d', 'Grade D')
    ], tracking=True)
    
    irrigation_source = fields.Selection([
        ('canal', 'Canal'),
        ('well', 'Well'),
        ('tube_well', 'Tube Well'),
        ('rainfed', 'Rainfed'),
        ('other', 'Other')
    ], tracking=True)
    
    crop_type = fields.Char('Crop Type', tracking=True)
    average_crop_yield = fields.Float('Average Crop Yield (per Ha)', tracking=True)
    market_value = fields.Monetary('Market Value (Rs.)', currency_field='currency_id', tracking=True)
    year_of_acquisition = fields.Integer('Year of Acquisition', tracking=True)
    land_value = fields.Monetary('Land Value (Rs.)', currency_field='currency_id', tracking=True)
    
    ownership_documents = fields.Selection([
        ('patta', 'Patta'),
        ('khatian', 'Khatian'),
        ('mutation', 'Mutation'),
        ('sale_deed', 'Sale Deed'),
        ('gift_deed', 'Gift Deed'),
        ('other', 'Other')
    ], tracking=True)
    
    remarks = fields.Text('Remarks', tracking=True)
    
    # Financial
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Related Records
    asset_ids = fields.One2many('larr.survey.asset', 'survey_id', string='Assets')
    
    # Computed Fields
    asset_count = fields.Integer(compute='_compute_asset_counts')
    tree_count = fields.Integer(compute='_compute_asset_counts')
    well_count = fields.Integer(compute='_compute_asset_counts')
    structure_count = fields.Integer(compute='_compute_asset_counts')
    crop_count = fields.Integer(compute='_compute_asset_counts')
    total_asset_value = fields.Monetary(compute='_compute_asset_counts', string='Total Asset Value')
    
    @api.depends('asset_ids')
    def _compute_asset_counts(self):
        for record in self:
            record.asset_count = len(record.asset_ids)
            record.tree_count = len(record.asset_ids.filtered(lambda x: x.asset_type == 'tree'))
            record.well_count = len(record.asset_ids.filtered(lambda x: x.asset_type == 'well'))
            record.structure_count = len(record.asset_ids.filtered(lambda x: x.asset_type == 'structure'))
            record.crop_count = len(record.asset_ids.filtered(lambda x: x.asset_type == 'crop'))
            record.total_asset_value = sum(record.asset_ids.mapped('total_value'))
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = str(uuid.uuid4())
        return super().create(vals_list)
    
    def action_in_progress(self):
        self.write({'survey_status': 'in_progress'})
    
    def action_complete(self):
        self.write({'survey_status': 'completed'})
    
    def action_cancel(self):
        self.write({'survey_status': 'cancelled'})


class LARRSurveyAsset(models.Model):
    _name = 'larr.survey.asset'
    _description = 'Survey Asset Management'
    _order = 'create_date desc'

    survey_id = fields.Many2one('larr.survey', 'Survey', required=True, ondelete='cascade')
    
    asset_type = fields.Selection([
        ('tree', 'Tree'),
        ('well', 'Well'),
        ('structure', 'Structure'),
        ('crop', 'Crop'),
        ('other', 'Other')
    ], required=True, tracking=True)
    
    category_type = fields.Selection([
        # Trees
        ('mango', 'Mango'),
        ('banana', 'Banana'),
        ('coconut', 'Coconut'),
        ('teak', 'Teak'),
        ('other_tree', 'Other Tree'),
        # Wells
        ('open_well', 'Open Well'),
        ('bore_well', 'Bore Well'),
        ('tube_well', 'Tube Well'),
        # Structures
        ('house', 'House'),
        ('shed', 'Shed'),
        ('fence', 'Fence'),
        ('other_structure', 'Other Structure'),
        # Crops
        ('paddy', 'Paddy'),
        ('wheat', 'Wheat'),
        ('maize', 'Maize'),
        ('other_crop', 'Other Crop')
    ], tracking=True)
    
    quantity = fields.Float('Quantity', default=1, tracking=True)
    unit = fields.Selection([
        ('piece', 'Piece'),
        ('kg', 'KG'),
        ('ton', 'Ton'),
        ('sq_m', 'Sq M'),
        ('sq_ft', 'Sq Ft'),
        ('acre', 'Acre'),
        ('hectare', 'Hectare')
    ], tracking=True)
    
    cost_per_unit = fields.Monetary('Cost per Unit (Rs.)', currency_field='currency_id', tracking=True)
    condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor')
    ], tracking=True)
    
    description = fields.Text('Description', tracking=True)
    
    # Computed Fields
    total_value = fields.Monetary(compute='_compute_total_value', string='Total Value', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    @api.depends('quantity', 'cost_per_unit')
    def _compute_total_value(self):
        for record in self:
            record.total_value = record.quantity * record.cost_per_unit


class LARRPackage(models.Model):
    _name = 'larr.package'
    _description = 'LARR Package'
    _order = 'name'

    name = fields.Char('Package Name', required=True, tracking=True)
    code = fields.Char('Package Code', tracking=True)
    description = fields.Text('Description')
    project_id = fields.Many2one('larr.project', 'Project', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)


class LARRSubPackage(models.Model):
    _name = 'larr.sub.package'
    _description = 'LARR Sub Package'
    _order = 'name'

    name = fields.Char('Sub Package Name', required=True, tracking=True)
    code = fields.Char('Sub Package Code', tracking=True)
    description = fields.Text('Description')
    package_id = fields.Many2one('larr.package', 'Package', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True) 


class LARROwner(models.Model):
    _name = 'larr.owner'
    _description = 'LARR Owner'
    _order = 'survey_id, is_main_owner desc, sequence, id'
    _rec_name = 'name'

    survey_id = fields.Many2one('larr.survey', 'Survey', required=True, ondelete='cascade')
    sequence = fields.Integer('Sequence', default=10)
    
    # Owner Type
    is_main_owner = fields.Boolean('Is Main Owner', default=True, tracking=True)
    
    # Basic Information
    name = fields.Char('Owner Name', required=True, tracking=True)
    name_kannada = fields.Char('Owner Name (Kannada)', tracking=True)
    father_husband_name = fields.Char('Father/Husband Name', tracking=True)
    father_husband_name_kannada = fields.Char('Father/Husband Name (Kannada)', tracking=True)
    relationship = fields.Selection([
        ('self', 'Self'),
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('husband', 'Husband'),
        ('wife', 'Wife'),
        ('son', 'Son'),
        ('daughter', 'Daughter'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
        ('other', 'Other')
    ], string='Relationship', default='self', tracking=True)
    
    # Contact Information
    mobile_number = fields.Char('Mobile Number', tracking=True)
    address = fields.Text('Address', tracking=True)
    
    # Identity Information
    identity_type = fields.Selection([
        ('aadhar', 'Aadhar Card'),
        ('pan', 'PAN Card'),
        ('voter_id', 'Voter ID'),
        ('driving_license', 'Driving License'),
        ('passport', 'Passport'),
        ('other', 'Other')
    ], string='Identity Type', tracking=True)
    identity_number = fields.Char('Identity Number', tracking=True)
    
    # Ownership Details
    share_percentage = fields.Float('Share Percentage (%)', tracking=True)
    
    # Status
    active = fields.Boolean('Active', default=True, tracking=True)
    
    # Related fields for easy access
    survey_name = fields.Char(related='survey_id.name', string='Survey', store=True)
    village_name = fields.Char(related='survey_id.village_id.name', string='Village', store=True)
    district_name = fields.Char(related='survey_id.district_id.name', string='District', store=True)
    
    @api.constrains('share_percentage')
    def _check_share_percentage(self):
        for record in self:
            if record.share_percentage and (record.share_percentage < 0 or record.share_percentage > 100):
                raise ValidationError(_('Share percentage must be between 0 and 100.'))
    
    @api.constrains('mobile_number')
    def _check_mobile_number(self):
        for record in self:
            if record.mobile_number and not record.mobile_number.isdigit():
                raise ValidationError(_('Mobile number should contain only digits.'))
    
    @api.onchange('is_main_owner')
    def _onchange_is_main_owner(self):
        if self.is_main_owner:
            self.relationship = 'self'
            self.share_percentage = 100.0
        else:
            self.relationship = 'other'
            self.share_percentage = 0.0
    
    def name_get(self):
        result = []
        for record in self:
            name = record.name
            if record.is_main_owner:
                name = f"{record.name} (Main Owner)"
            else:
                name = f"{record.name} (Additional Owner)"
            if record.share_percentage:
                name = f"{name} ({record.share_percentage}%)"
            result.append((record.id, name))
        return result
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Auto-set relationship for main owner
            if vals.get('is_main_owner'):
                vals['relationship'] = 'self'
        return super().create(vals_list) 