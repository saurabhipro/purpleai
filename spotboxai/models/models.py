# # -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class InheritResPartner(models.Model):
   _inherit = 'res.partner'

   state_id = fields.Many2one(string='State', domain="[('country_id','=',233)]")

class InheritAccountTaxInherit(models.Model):
   _inherit = 'account.tax'

   state = fields.Many2one('res.country.state', string="State(Province)", domain=[('country_id','=',233)])
   city = fields.Char(string="City")


   @api.constrains('city')
   def _check_unique_city(self):
      for record in self:
         if record.city:
               city_lower = record.city.lower()
               duplicate_records = self.search([
                  ('id', '!=', record.id), 
                  ('city', 'ilike', record.city)  
               ])
               
               if duplicate_records:
                  raise ValidationError(
                     f"City '{record.city}' already exists. City names should be unique."
                  )
         if record.state:
            duplicate_state = self.search([
               ('id', '!=', record.id), 
               ('state', '=', record.state.id)
            ])
            if duplicate_state:
               raise ValidationError(
                  f"Province '{record.state.name}' already exists. Province names should be unique."
               )

class AccountMoveInherit(models.Model):
   _inherit = 'account.move'
               

   @api.onchange('invoice_line_ids', 'partner_id')
   def action_tax_onchange(self):
      for move in self:
         if move.partner_id:
            for line in move.invoice_line_ids:
               if line.partner_id.city:
                     tax_ids_city = self.env['account.tax'].sudo().search([('city', '=', line.partner_id.city)]).ids
                     if tax_ids_city:
                        line.tax_ids = [(6, 0, tax_ids_city)]

                     else:
                        tax_ids_state = self.env['account.tax'].sudo().search([('state', '=', line.partner_id.state_id.id)]).ids
                        if tax_ids_state:
                           line.tax_ids = [(6, 0, tax_ids_state)]
                        else:
                           pass



   
class InheritPicking(models.Model):
   _inherit = 'stock.picking'

   date_done = fields.Datetime('Date of Transfer', copy=False, readonly=False, help="Date at which the transfer has been processed or cancelled.")
   scheduled_date = fields.Datetime(
        'Scheduled Date', compute='_compute_scheduled_date', inverse='_set_scheduled_date', store=True,
        index=True, default=fields.Datetime.now, tracking=True,readonly=False,
        help="Scheduled time for the first part of the shipment to be processed. Setting manually a value here would set it as expected date for all the stock moves.")
    



   
