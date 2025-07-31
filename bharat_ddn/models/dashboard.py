from odoo import models, fields, api
import itertools
from datetime import datetime, timedelta
from datetime import date, timedelta


class Dashboard(models.Model):
    _inherit = 'ddn.property.info'


  
    @api.model
    def get_dashboard_data(self):
        PropertyInfo = self.env['ddn.property.info'].search([])
        sorted_records = sorted(PropertyInfo, key=lambda rec: rec.ward_id.name if rec.ward_id else '')
        grouped_records = itertools.groupby(sorted_records, key=lambda rec: rec.ward_id.name if rec.ward_id else '') 
        result = {}

        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        surveys_today = self.env['ddn.property.survey'].search_count([
            ('create_date', '>=', today_start),
            ('create_date', '<=', today_end)
        ])

        active_surveyors_today = len(set(self.env['ddn.property.survey'].search([
            ('create_date', '>=', today_start),
            ('create_date', '<=', today_end)
        ]).mapped('surveyer_id')))

        total_surveyors = self.env['res.users'].search_count([('is_surveyor', '=', True)])

        qr_scan_env = self.env['ddn.qr.scan']
        qr_scans_today = qr_scan_env.search_count([
            ('scan_time', '>=', today_start),
            ('scan_time', '<=', today_end)
        ])
        total_qr_scans = qr_scan_env.search_count([])

        unique_uuids_today = set(qr_scan_env.search([
            ('scan_time', '>=', today_start),
            ('scan_time', '<=', today_end)
        ]).mapped('uuid'))
        unique_qr_scans_today = len(unique_uuids_today)

        unique_uuids_all = set(qr_scan_env.search([]).mapped('uuid'))
        unique_qr_scans = len(unique_uuids_all)

        surveyed_per_day = []
        Survey = self.env['ddn.property.survey']
        for i in range(13, -1, -1):
            day = today - timedelta(days=i)
            day_start = datetime.combine(day, datetime.min.time())
            day_end = datetime.combine(day, datetime.max.time())
            count = Survey.search_count([
                ('create_date', '>=', day_start),
                ('create_date', '<=', day_end)
            ])
            surveyed_per_day.append({'date': day.strftime('%Y-%m-%d'), 'count': count})

        for group_key, grp in grouped_records:
            count = 0
            new = 0
            uploaded = 0
            pdf_downloaded = 0
            surveyed = 0
            unlocked = 0
            discovered = 0
            ward_zone_name = None

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
                'zone': ward_zone_name
            }

        # Prepare total status counts for pie chart
        total_uploaded = self.env['ddn.property.info'].search_count([('property_status', '=', 'uploaded')])
        total_pdf_downloaded = self.search_count([('property_status', '=', 'pdf_downloaded')])
        total_surveyed = self.search_count([('property_status', '=', 'surveyed')])
        total_unlocked = self.search_count([('property_status', '=', 'unlocked')])
        total_discovered = self.search_count([('property_status', '=', 'discovered')])

        final_result = [{
            'total_count': self.env['ddn.property.info'].search_count([]),
            'total_uploaded': total_uploaded,
            'total_pdf_downloaded': total_pdf_downloaded,
            'total_surveyed': total_surveyed,
            'total_unlocked': total_unlocked,
            'total_discovered': total_discovered,
            'total_visit_again': self.search_count([('property_status', '=', 'visit_again')]),
            'total_zones': self.env['ddn.zone'].search_count([]),
            'total_wards': self.env['ddn.ward'].search_count([]),
            'total_colonies': self.env['ddn.colony'].search_count([]),
            'total_surveyors': f"{total_surveyors} / {active_surveyors_today}",
            'surveys_today': surveys_today,
            'total_qr_scans_today': qr_scans_today,
            'unique_qr_scans_today': unique_qr_scans_today,
            'total_qr_scans': total_qr_scans,
            'unique_qr_scans': unique_qr_scans,
            'surveyed_per_day': surveyed_per_day,
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
            ],
            # ✅ Add pie chart data here:
            'pie_data': [
                {'label': 'Uploaded', 'value': total_uploaded},
                {'label': 'PDF Downloaded', 'value': total_pdf_downloaded},
                {'label': 'Surveyed', 'value': total_surveyed},
                {'label': 'Unlocked', 'value': total_unlocked},
                {'label': 'Discovered', 'value': total_discovered},
            ]
        }]

        print("===== ", final_result)
        return final_result


    # @api.model
    # def get_survey_stats(self, start_date=None, end_date=None, group_by='day'):
    #     # Get current month range if not passed
    #     today = date.today()
    #     if not start_date:
    #         start_date = today.replace(day=1).strftime('%Y-%m-%d')
    #     if not end_date:
    #         next_month = today.replace(day=28) + timedelta(days=4)
    #         end_date = (next_month.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')

    #     # Choose grouping format
    #     group_sql = {
    #         'day': "TO_CHAR(DATE(s.create_date), 'YYYY-MM-DD')",
    #         'month': "TO_CHAR(DATE_TRUNC('month', s.create_date), 'YYYY-MM')",
    #         'year': "TO_CHAR(DATE_TRUNC('year', s.create_date), 'YYYY')",
    #     }.get(group_by, "TO_CHAR(DATE(s.create_date), 'YYYY-MM-DD')")

    #     query = f"""
    #         SELECT {group_sql} AS period, COUNT(*)
    #         FROM ddn_property_survey s
    #         JOIN ddn_property_info p ON s.property_id = p.id
    #         WHERE s.create_date BETWEEN %s AND %s
    #         AND p.property_status = 'surveyed'
    #         GROUP BY period
    #         ORDER BY period
    #     """

    #     self.env.cr.execute(query, (start_date, end_date))
    #     result = self.env.cr.fetchall()

    #     # Return format expected by chart component
    #     return [{'label': r[0], 'value': r[1]} for r in result]
    
    @api.model
    def get_survey_stats(self):
        # Format directly for the GraphComponent
        data = [
            {'label': '01-07-2025', 'value': 5},
            {'label': '02-07-2025', 'value': 10},
            {'label': '03-07-2025', 'value': 7},
            {'label': '04-07-2025', 'value': 12},
        ]
        return {'chart_data': data}