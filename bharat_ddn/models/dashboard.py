from odoo import models, fields, api
import itertools
from datetime import datetime, timedelta


class Dashboard(models.Model):
    _inherit = 'ddn.property.info'


    @api.model
    def get_dashboard_data(self):
        PropertyInfo = self.env['ddn.property.info'].search([])
        sorted_records = sorted(PropertyInfo, key=lambda rec: rec.ward_id.name if rec.ward_id else '')
        grouped_records = itertools.groupby(sorted_records, key=lambda rec: rec.ward_id.name if rec.ward_id else '') 
        result = {}

        # Calculate today's date range
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        # Calculate today's surveys
        surveys_today = self.env['ddn.property.survey'].search_count([
            ('create_date', '>=', today_start),
            ('create_date', '<=', today_end)
        ])

        # Calculate today's QR scans
        qr_scan_env = self.env['ddn.qr.scan']
        qr_scans_today = qr_scan_env.search_count([
            ('scan_time', '>=', today_start),
            ('scan_time', '<=', today_end)
        ])
        total_qr_scans = qr_scan_env.search_count([])
        # Unique property uuids scanned today (count each uuid only once, even if scanned multiple times)
        unique_uuids_today = set(qr_scan_env.search([
            ('scan_time', '>=', today_start),
            ('scan_time', '<=', today_end)
        ]).mapped('uuid'))
        unique_qr_scans_today = len(unique_uuids_today)

        for group_key, grp in grouped_records:
            count = 0
            new = 0
            uploaded = 0
            pdf_downloaded = 0
            surveyed = 0
            unlocked = 0
            discovered = 0
            ward_zone_name = None  # Add zone

            for rec in grp:
                count += 1
                if rec.property_status == 'new':
                    new += 1
                if rec.property_status == 'uploaded':
                    uploaded += 1
                if rec.property_status == 'pdf_downloaded':
                    pdf_downloaded += 1
                if rec.property_status == 'surveyed':
                    surveyed += 1
                if rec.property_status == 'unlocked':
                    unlocked += 1
                if rec.property_status == 'discovered':
                    discovered += 1

                if not ward_zone_name and rec.ward_id and rec.ward_id.zone_id:
                    ward_zone_name = rec.ward_id.zone_id.name

            result[group_key] = {
                'count': count,
                'new': new,
                'uploaded': uploaded,
                'pdf_downloaded': pdf_downloaded,
                'surveyed': surveyed,
                'unlocked': unlocked,
                'discovered': discovered,
                'zone': ward_zone_name  # Include zone in result
            }

        final_result = [{
            'total_count': self.env['ddn.property.info'].search_count([]),
            'total_uploaded': self.env['ddn.property.info'].search_count([('property_status', '=', 'uploaded')]),
            'total_pdf_downloaded': self.search_count([('property_status', '=', 'pdf_downloaded')]),
            'total_surveyed': self.search_count([('property_status', '=', 'surveyed')]),
            'total_unlocked': self.search_count([('property_status', '=', 'unlocked')]),
            'total_discovered': self.search_count([('property_status', '=', 'discovered')]),
            'total_visit_again': self.search_count([('property_status', '=', 'visit_again')]),
            'total_zones': self.env['ddn.zone'].search_count([]),
            'total_wards': self.env['ddn.ward'].search_count([]),
            'total_users': self.env['res.users'].search_count([]),
            'surveys_today': surveys_today,
            'total_qr_scans_today': qr_scans_today,
            'unique_qr_scans_today': unique_qr_scans_today,
            'total_qr_scans': total_qr_scans,
            'ward_data': [
                {
                    'ward': ward,
                    'zone': data.get('zone'),
                    'total_count': data['count'],
                    'uploaded_count': data['uploaded'],
                    'pdf_downloaded_count': data['pdf_downloaded'],
                    'surveyed_count': data['surveyed'],
                    'unlocked_count': data['unlocked'],
                    'discovered_count': data['discovered'],
                } for ward, data in result.items()
            ]
        }]

        print("result - ", final_result)
        return final_result
