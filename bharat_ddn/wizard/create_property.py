from odoo import models, fields, api

from odoo.exceptions import ValidationError



class PropertyCreateWizard(models.TransientModel):
    _name = 'property.create.wizard'
    _description = 'Wizard to Create property data'


    no_of_property = fields.Integer(string="No of Property")
    zone_id = fields.Many2one('ddn.zone', string="Zone")
    colony_id = fields.Many2one('ddn.colony', string="Colony")
    ward_id = fields.Many2one('ddn.ward', string="Ward")




    def action_create(self):
        for rec in self:
            if not rec.zone_id or not rec.ward_id or not rec.colony_id:
                raise ValidationError("Please select zone, ward and colony first.")

            # Get last UPIC for this zone/ward/colony
            last_property = self.env['ddn.property.info'].search([('zone_id', '=', rec.zone_id.id),('ward_id', '=', rec.ward_id.id),('colony_id', '=', rec.colony_id.id)],order='id desc',limit=1)

            if last_property:
                last_upic_no = last_property.upic_no
                last_seq = int(last_upic_no[-4:])  # last 4 digits
            else:
                last_seq = 0

            # Now start from the last sequence
            new_seq = last_seq

            if rec.no_of_property:
                for i in range(rec.no_of_property):
                    new_seq += 1
                    new_upic_no = f"{last_upic_no[:-4]}{new_seq:04d}" if last_property else f"{rec.zone_id.code}{rec.ward_id.code}{rec.colony_id.code}{new_seq:04d}"
                    
                    self.env['ddn.property.info'].create({
                        'upic_no': new_upic_no,
                        'zone_id': rec.zone_id.id,
                        'ward_id': rec.ward_id.id,
                        'colony_id': rec.colony_id.id,
                    })
