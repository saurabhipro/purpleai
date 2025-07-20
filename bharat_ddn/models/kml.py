from odoo import models, fields, api
import itertools
from datetime import datetime, timedelta


class Dashboard(models.Model):
    _inherit = 'ddn.property.info'


    def get_kml_properties(self, zone_id=None, ward_id=None, status=None):
        domain = [
            ('latitude', '!=', False),
            ('longitude', '!=', False),
            ('latitude', '!=', ''),
            ('longitude', '!=', '')
        ]

        # Optional: Add zone/ward/status filters if provided
        if zone_id:
            domain.append(('zone_id', '=', zone_id))
        if ward_id:
            domain.append(('ward_id', '=', ward_id))
        if status:
            domain.append(('status', '=', status))

        return self.sudo().search_read(
            domain,
            fields=['id', 'upic_no', 'owner_name', 'latitude', 'longitude']
        )