from odoo import models, fields
from datetime import datetime
import io
import base64
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
import pytz



class DdnReport(models.TransientModel):
    _name = 'ddn.report'
    _description = 'DDN Report Wizard'

    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    zone_id = fields.Many2many('ddn.zone', string='Zone')
    ward_id = fields.Many2many('ddn.ward', string='Ward')


    def generate_xlsx_report(self):
        # Create workbook and sheet
        wb = Workbook()
        ws = wb.active
        ws.title = "Survey Report"

        # Styles
        header_fill = PatternFill(start_color="D3D3D3", end_color="D3D3D3", fill_type="solid")
        green_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")  # Light green
        red_fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid")    # Light red
        orange_fill = PatternFill(start_color="FFD700", end_color="FFD700", fill_type="solid")  # Gold/Orange for visit again
        border = Border(left=Side(style='thin'), right=Side(style='thin'),
                        top=Side(style='thin'), bottom=Side(style='thin'))
        
        header_font = Font(bold=True)
        title_font = Font(bold=True, size=25)
        align_left = Alignment(horizontal="left", vertical="center")

        # Title Row
        ws.merge_cells('A2:T2')  # Updated to accommodate new columns
        title_cell = ws['A2']
        title_cell.value = "Survey Report"
        title_cell.font = title_font
        title_cell.fill = header_fill
        title_cell.alignment = align_left
        title_cell.border = border

        # Date Range
        ws.cell(row=4, column=1, value="Date From").border = border
        ws.cell(row=4, column=1).alignment = align_left
        ws.cell(row=4, column=2, value=self.date_from.strftime('%d-%m-%Y') if self.date_from else "").border = border
        ws.cell(row=5, column=1, value="Date To").border = border
        ws.cell(row=5, column=2, value=self.date_to.strftime('%d-%m-%Y') if self.date_to else "").border = border

        # Headers
        headers = [
            "UPIC No", "Property Id", "Zone", "Ward", "Colony", "Owner Name", 
            "Father Name", "Mobile No", "Address Line 1", "Address Line 2", 
            "Latitude", "Longitude", "Total Floors", "Floor Number", 
            "Surveyor", "Surveyor Datetime", "Property Type", "Microsite Url",
            "Property Status", "Is Solar", "Is Rain Water Harvesting"
        ]

        header_row = 7
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=header_row, column=col_num, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_left
            cell.border = border

        # Get Data
        domain = [('company_id', '=', self.company_id.id)]
        if self.zone_id:
            domain += [('property_id.zone_id', 'in', self.zone_id.ids)]
        if self.ward_id:
            domain += [('property_id.ward_id', 'in', self.ward_id.ids)]
        if self.date_from:
            domain += [('create_date', '>=', self.date_from)]
        if self.date_to:
            domain += [('create_date', '<=', self.date_to)]

        records = self.env['ddn.property.survey'].search(domain)

        row = header_row + 1
        for rec in records:
            prop = rec.property_id
            values = [
                prop.upic_no or '',
                prop.property_id or '',
                prop.zone_id.name or '',
                prop.ward_id.name or '',
                prop.colony_id.name or '',
                rec.owner_name or '',
                rec.father_name or '',
                rec.mobile_no or '',
                rec.address_line_1 or '',
                rec.address_line_2 or '',
                rec.latitude or '',
                rec.longitude or '',
                rec.total_floors or '',
                rec.floor_number or '',
                rec.surveyer_id.name or '',
                rec.create_date.strftime('%d-%m-%Y %H:%M:%S') if rec.create_date else '',
                prop.property_type.name or '',
                prop.microsite_url or '',
                prop.property_status or '',
                'Yes' if rec.is_solar else 'No',
                'Yes' if rec.is_rainwater_harvesting else 'No',
            ]

            for col_num, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col_num, value=val)
                cell.border = border
                cell.alignment = align_left
                
                # Apply color coding for Property Status column
                if col_num == 19:  # Property Status column
                    if prop.property_status == 'surveyed':
                        cell.fill = green_fill
                    elif prop.property_status == 'visit_again':
                        cell.fill = orange_fill
                
                # Apply color coding for solar and rainwater harvesting columns
                elif col_num == 20:  # Is Solar column
                    cell.fill = green_fill if rec.is_solar else red_fill
                elif col_num == 21:  # Is Rain Water Harvesting column
                    cell.fill = green_fill if rec.is_rainwater_harvesting else red_fill
                    
            row += 1

        # Prepare output for download
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        file_base64 = base64.b64encode(output.read()).decode('utf-8')

        # Attachment
        calcuttaTz = pytz.timezone("Asia/Kolkata")
        filename = f"Survey_Report_{datetime.now(calcuttaTz).strftime('%d-%m-%Y_%H:%M:%S')}.xlsx"

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': file_base64,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }