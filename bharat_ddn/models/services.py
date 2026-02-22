from odoo import models, fields

class GovtWard(models.Model):
    _name = 'ddn.services'
    _description = 'DDN Services'

    company_id = fields.Many2one('res.company', string="Company", default=lambda self : self.env.company.id)
    name = fields.Char(string="Name")
    header = fields.Char(string="Header1")
    header2 = fields.Char(string="Header2")
    sub_header = fields.Char(string="Sub Header")
    govt_line_ids = fields.One2many('govt.line', 'service_id', string="Govt. Service")
    tracking_line_ids = fields.One2many('tracking.line', 'service_id', string="Tracking Service")
    know_officer_line_ids = fields.One2many('know.officer.line', 'service_id', string="Your Officer Service")
    dial_line_ids = fields.One2many('dial.officer.line', 'service_id', string="Dial Service")
    other_line_ids = fields.One2many('other.officer.line', 'service_id', string="Other Service")
    banner_line_ids = fields.One2many('banner.officer.line', 'service_id', string="Banner Service")



class GovtLine(models.Model):
    _name = 'govt.line'
    _description = 'Govt Service Line'

    name = fields.Char(string="Name")
    text = fields.Text(string="Text")
    hyperlink = fields.Char(string="Hyperlink")
    icon = fields.Char(string="Icon")
    is_global = fields.Boolean(string="Is Global", default=False)
    is_active = fields.Boolean(string="Is Active", default=True)
    service_id = fields.Many2one('ddn.services', string="Service")


class TrackingLine(models.Model):
    _name = 'tracking.line'
    _description = 'Tracking Service Line'

    name = fields.Char(string="Name")
    text = fields.Text(string="Text")
    hyperlink = fields.Char(string="Hyperlink")
    icon = fields.Char(string="Icon")
    is_global = fields.Boolean(string="Is Global", default=False)
    is_active = fields.Boolean(string="Is Active", default=True)
    service_id = fields.Many2one('ddn.services', string="Service")


class KnowOfficerLine(models.Model):
    _name = 'know.officer.line'
    _description = 'Know Your Officer Service Line'

    header = fields.Char(string="Header")
    name = fields.Char(string="Name")
    mobile = fields.Char(string="Mobile")
    icon = fields.Char(string="Icon")
    text = fields.Text(string="Text")
    hyperlink = fields.Char(string="Hyperlink")
    is_global = fields.Boolean(string="Is Global", default=False)
    is_active = fields.Boolean(string="Is Active", default=True)
    service_id = fields.Many2one('ddn.services', string="Service")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self : self.env.company.id)
    zone_id = fields.Many2one('ddn.zone', string='Zone')
    ward_id = fields.Many2one('ddn.ward',string='Ward')


class DialOfficerLine(models.Model):
    _name = 'dial.officer.line'
    _description = 'Dial Officer Service Line'

    name = fields.Char(string="Name")
    text = fields.Text(string="Text")
    mobile = fields.Char(string="Mobile")
    hyperlink = fields.Char(string="Hyperlink")
    icon = fields.Char(string="Icon")
    is_global = fields.Boolean(string="Is Global", default=False)
    is_active = fields.Boolean(string="Is Active", default=True)
    service_id = fields.Many2one('ddn.services', string="Service")
    bg_color = fields.Char(string="BG-Color")


class OtherOfficerLine(models.Model):
    _name = 'other.officer.line'
    _description = 'Other Officer Service Line'

    name = fields.Char(string="Name")
    text = fields.Text(string="Text")
    hyperlink = fields.Char(string="Hyperlink")
    icon = fields.Char(string="Icon")
    is_global = fields.Boolean(string="Is Global", default=False)
    is_active = fields.Boolean(string="Is Active", default=True)
    service_id = fields.Many2one('ddn.services', string="Service")


class BannerOfficerLine(models.Model):
    _name = 'banner.officer.line'
    _description = 'Banner Service Line'

    name = fields.Char(string="Name")
    text = fields.Text(string="Text")
    hyperlink = fields.Char(string="Hyperlink")
    icon = fields.Binary(string="BG Image")
    is_global = fields.Boolean(string="Is Global", default=False)
    is_active = fields.Boolean(string="Is Active", default=True)
    service_id = fields.Many2one('ddn.services', string="Service")






