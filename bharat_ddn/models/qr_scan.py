from odoo import models, fields

class QRScan(models.Model):
    _name = 'ddn.qr.scan'
    _description = 'QR Code Scan Log'
    _order = 'scan_time desc'

    uuid = fields.Char('UUID', required=True)
    scan_url = fields.Char('Scanned URL', required=True)
    scan_time = fields.Datetime('Scan Time', default=fields.Datetime.now)
    property_id = fields.Many2one('ddn.property.info', string='Property')
    upic_no = fields.Char('UPIC No', related='property_id.upic_no', store=True, readonly=True) 