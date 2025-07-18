from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


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