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


    @api.model
    def get_survey_stats(self, start_date=None, end_date=None, group_by='day'):
        # Get current month range if not passed
        today = date.today()
        if not start_date:
            start_date = today.replace(day=1).strftime('%Y-%m-%d')
        if not end_date:
            next_month = today.replace(day=28) + timedelta(days=4)
            end_date = (next_month.replace(day=1) - timedelta(days=1)).strftime('%Y-%m-%d')

        # Choose grouping format
        group_sql = {
            'day': "TO_CHAR(DATE(s.create_date), 'YYYY-MM-DD')",
            'month': "TO_CHAR(DATE_TRUNC('month', s.create_date), 'YYYY-MM')",
            'year': "TO_CHAR(DATE_TRUNC('year', s.create_date), 'YYYY')",
        }.get(group_by, "TO_CHAR(DATE(s.create_date), 'YYYY-MM-DD')")

        query = f"""
            SELECT {group_sql} AS period, COUNT(*)
            FROM ddn_property_survey s
            JOIN ddn_property_info p ON s.property_id = p.id
            WHERE s.create_date BETWEEN %s AND %s
            AND p.property_status = 'surveyed'
            GROUP BY period
            ORDER BY period
        """

        self.env.cr.execute(query, (start_date, end_date))
        result = self.env.cr.fetchall()

        # Return format expected by chart component
        return [{'label': r[0], 'value': r[1]} for r in result]
    
from collections import defaultdict
from datetime import datetime
from odoo import models, api


class PropertySurvey(models.Model):
    _inherit = 'ddn.property.survey'  # If extending

    @api.model
    def get_survey_stats(self, start_date=None, end_date=None, group_by='day'):
        domain = [('company_id', '=', self.env.company.id)]

        if start_date:
            domain.append(('create_date', '>=', start_date))
        if end_date:
            domain.append(('create_date', '<=', end_date))

        # Optional filters from context or additional params
        zone_id = self.env.context.get('zone_id')
        ward_id = self.env.context.get('ward_id')

        if zone_id:
            domain.append(('property_id.zone_id', 'in', zone_id if isinstance(zone_id, list) else [zone_id]))
        if ward_id:
            domain.append(('property_id.ward_id', 'in', ward_id if isinstance(ward_id, list) else [ward_id]))

        # Step 1: Search all matching surveys
        survey_records = self.env['ddn.property.survey'].search(domain)
        unique_property_ids = survey_records.mapped('property_id.id')

        # Step 2: Get latest survey per property
        records = []
        for property_id in unique_property_ids:
            property_surveys = survey_records.filtered(lambda r: r.property_id.id == property_id)
            latest_survey = max(property_surveys, key=lambda r: r.create_date)
            records.append(latest_survey)

        # Step 3: Summaries
        surveyor_counts = {}
        status_counts = {}
        type_counts = {}
        day_status_counts = defaultdict(lambda: defaultdict(int))
        all_statuses = set()

        for rec in records:
            # Surveyor
            name = rec.surveyer_id.name or 'Unknown'
            surveyor_counts[name] = surveyor_counts.get(name, 0) + 1

            # Property status
            status = rec.property_id.property_status or 'Unknown'
            status_counts[status] = status_counts.get(status, 0) + 1

            # Property type
            ptype = rec.property_id.property_type.name or 'Unknown'
            type_counts[ptype] = type_counts.get(ptype, 0) + 1

            # Day-wise data
            if rec.create_date:
                if group_by == 'month':
                    day = rec.create_date.strftime('%Y-%m')
                elif group_by == 'year':
                    day = rec.create_date.strftime('%Y')
                else:
                    day = rec.create_date.strftime('%d-%m-%Y')

                day_status_counts[day][status] += 1
                all_statuses.add(status)

        # Step 4: Structure day-wise data
        days_sorted = sorted(day_status_counts.keys(), key=lambda d: datetime.strptime(d, '%d-%m-%Y') if group_by == 'day' else datetime.strptime(d, '%Y-%m') if group_by == 'month' else datetime.strptime(d, '%Y'))
        all_statuses = sorted(all_statuses)
        print("\n \n all_statuses - ", all_statuses)

        daywise_data = []
        for day in days_sorted:
            entry = {"date": day}
            for status in all_statuses:
                entry[status] = day_status_counts[day].get(status, 0)
            daywise_data.append(entry)

        # Step 5: Return structured data
        return {
            "surveyor_counts": surveyor_counts,
            "status_counts": status_counts,
            "type_counts": type_counts,
            "daywise_data": daywise_data,
            "statuses": all_statuses,
        }
