from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class LARRReportWizard(models.TransientModel):
    _name = 'larr.report.wizard'
    _description = 'LARR Report Wizard'

    report_type = fields.Selection([
        ('project_summary', 'Project Summary Report'),
        ('acquisition_status', 'Acquisition Status Report'),
        ('compensation_summary', 'Compensation Summary Report'),
        ('rehabilitation_status', 'Rehabilitation Status Report'),
        ('stakeholder_analysis', 'Stakeholder Analysis Report'),
        ('financial_summary', 'Financial Summary Report')
    ], required=True, string='Report Type')
    
    project_id = fields.Many2one('larr.project', 'Project')
    date_from = fields.Date('Date From')
    date_to = fields.Date('Date To', default=fields.Date.today)
    
    group_by = fields.Selection([
        ('project', 'Project'),
        ('acquisition_type', 'Acquisition Type'),
        ('compensation_type', 'Compensation Type'),
        ('rehabilitation_type', 'Rehabilitation Type'),
        ('stakeholder_type', 'Stakeholder Type'),
        ('month', 'Month'),
        ('quarter', 'Quarter'),
        ('year', 'Year')
    ], string='Group By')
    
    include_draft = fields.Boolean('Include Draft Records', default=True)
    include_cancelled = fields.Boolean('Include Cancelled Records', default=False)
    
    def action_generate_report(self):
        """Generate the selected report"""
        if self.report_type == 'project_summary':
            return self._generate_project_summary_report()
        elif self.report_type == 'acquisition_status':
            return self._generate_acquisition_status_report()
        elif self.report_type == 'compensation_summary':
            return self._generate_compensation_summary_report()
        elif self.report_type == 'rehabilitation_status':
            return self._generate_rehabilitation_status_report()
        elif self.report_type == 'stakeholder_analysis':
            return self._generate_stakeholder_analysis_report()
        elif self.report_type == 'financial_summary':
            return self._generate_financial_summary_report()
    
    def _generate_project_summary_report(self):
        """Generate project summary report"""
        domain = []
        if self.project_id:
            domain.append(('id', '=', self.project_id.id))
        if self.date_from:
            domain.append(('create_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('create_date', '<=', self.date_to))
        
        projects = self.env['larr.project'].search(domain)
        
        # Prepare data for report
        data = {
            'report_type': 'Project Summary Report',
            'date_from': self.date_from,
            'date_to': self.date_to,
            'projects': []
        }
        
        for project in projects:
            project_data = {
                'name': project.name,
                'code': project.code,
                'type': dict(project._fields['project_type'].selection).get(project.project_type),
                'state': dict(project._fields['state'].selection).get(project.state),
                'total_area': project.total_area_required,
                'estimated_cost': project.estimated_cost,
                'progress': project.progress_percentage,
                'acquisition_count': project.acquisition_count,
                'rehabilitation_count': project.rehabilitation_count,
                'stakeholder_count': project.stakeholder_count,
            }
            data['projects'].append(project_data)
        
        return self._print_report('larr.report_project_summary', data)
    
    def _generate_acquisition_status_report(self):
        """Generate acquisition status report"""
        domain = []
        if self.project_id:
            domain.append(('project_id', '=', self.project_id.id))
        if self.date_from:
            domain.append(('create_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('create_date', '<=', self.date_to))
        
        acquisitions = self.env['larr.land.acquisition'].search(domain)
        
        data = {
            'report_type': 'Acquisition Status Report',
            'date_from': self.date_from,
            'date_to': self.date_to,
            'acquisitions': []
        }
        
        for acquisition in acquisitions:
            acquisition_data = {
                'name': acquisition.name,
                'project': acquisition.project_id.name,
                'land_owner': acquisition.land_owner_id.name,
                'land_area': acquisition.land_area,
                'land_type': dict(acquisition._fields['land_type'].selection).get(acquisition.land_type),
                'acquisition_type': dict(acquisition._fields['acquisition_type'].selection).get(acquisition.acquisition_type),
                'state': dict(acquisition._fields['state'].selection).get(acquisition.state),
                'compensation_amount': acquisition.compensation_amount,
                'compensation_status': dict(acquisition._fields['compensation_status'].selection).get(acquisition.compensation_status),
            }
            data['acquisitions'].append(acquisition_data)
        
        return self._print_report('larr.report_acquisition_status', data)
    
    def _generate_compensation_summary_report(self):
        """Generate compensation summary report"""
        domain = []
        if self.project_id:
            domain.append(('acquisition_id.project_id', '=', self.project_id.id))
        if self.date_from:
            domain.append(('create_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('create_date', '<=', self.date_to))
        
        compensations = self.env['larr.compensation'].search(domain)
        
        data = {
            'report_type': 'Compensation Summary Report',
            'date_from': self.date_from,
            'date_to': self.date_to,
            'compensations': []
        }
        
        for compensation in compensations:
            compensation_data = {
                'name': compensation.name,
                'project': compensation.acquisition_id.project_id.name,
                'acquisition': compensation.acquisition_id.name,
                'beneficiary': compensation.beneficiary_id.name,
                'type': dict(compensation._fields['compensation_type'].selection).get(compensation.compensation_type),
                'amount': compensation.amount,
                'state': dict(compensation._fields['state'].selection).get(compensation.state),
                'payment_method': dict(compensation._fields['payment_method'].selection).get(compensation.payment_method),
                'payment_date': compensation.payment_date,
            }
            data['compensations'].append(compensation_data)
        
        return self._print_report('larr.report_compensation_summary', data)
    
    def _generate_rehabilitation_status_report(self):
        """Generate rehabilitation status report"""
        domain = []
        if self.project_id:
            domain.append(('project_id', '=', self.project_id.id))
        if self.date_from:
            domain.append(('create_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('create_date', '<=', self.date_to))
        
        rehabilitations = self.env['larr.rehabilitation'].search(domain)
        
        data = {
            'report_type': 'Rehabilitation Status Report',
            'date_from': self.date_from,
            'date_to': self.date_to,
            'rehabilitations': []
        }
        
        for rehabilitation in rehabilitations:
            rehabilitation_data = {
                'name': rehabilitation.name,
                'project': rehabilitation.project_id.name,
                'affected_person': rehabilitation.affected_person_id.name,
                'family_members': rehabilitation.family_members,
                'rehabilitation_type': dict(rehabilitation._fields['rehabilitation_type'].selection).get(rehabilitation.rehabilitation_type),
                'state': dict(rehabilitation._fields['state'].selection).get(rehabilitation.state),
                'current_land_area': rehabilitation.current_land_area,
                'new_land_area': rehabilitation.new_land_area,
                'completion_date': rehabilitation.completion_date,
            }
            data['rehabilitations'].append(rehabilitation_data)
        
        return self._print_report('larr.report_rehabilitation_status', data)
    
    def _generate_stakeholder_analysis_report(self):
        """Generate stakeholder analysis report"""
        domain = []
        if self.project_id:
            domain.append(('project_id', '=', self.project_id.id))
        
        stakeholders = self.env['larr.stakeholder'].search(domain)
        
        data = {
            'report_type': 'Stakeholder Analysis Report',
            'stakeholders': []
        }
        
        for stakeholder in stakeholders:
            stakeholder_data = {
                'name': stakeholder.name,
                'project': stakeholder.project_id.name,
                'type': dict(stakeholder._fields['stakeholder_type'].selection).get(stakeholder.stakeholder_type),
                'engagement_level': dict(stakeholder._fields['engagement_level'].selection).get(stakeholder.engagement_level),
                'state': dict(stakeholder._fields['state'].selection).get(stakeholder.state),
                'contact_person': stakeholder.contact_person,
                'phone': stakeholder.phone,
                'email': stakeholder.email,
            }
            data['stakeholders'].append(stakeholder_data)
        
        return self._print_report('larr.report_stakeholder_analysis', data)
    
    def _generate_financial_summary_report(self):
        """Generate financial summary report"""
        domain = []
        if self.project_id:
            domain.append(('acquisition_id.project_id', '=', self.project_id.id))
        if self.date_from:
            domain.append(('create_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('create_date', '<=', self.date_to))
        
        compensations = self.env['larr.compensation'].search(domain)
        
        # Calculate totals
        total_compensation = sum(compensations.mapped('amount'))
        paid_compensation = sum(compensations.filtered(lambda x: x.state == 'paid').mapped('amount'))
        pending_compensation = sum(compensations.filtered(lambda x: x.state in ['draft', 'approved']).mapped('amount'))
        
        data = {
            'report_type': 'Financial Summary Report',
            'date_from': self.date_from,
            'date_to': self.date_to,
            'total_compensation': total_compensation,
            'paid_compensation': paid_compensation,
            'pending_compensation': pending_compensation,
            'compensations': []
        }
        
        for compensation in compensations:
            compensation_data = {
                'name': compensation.name,
                'project': compensation.acquisition_id.project_id.name,
                'type': dict(compensation._fields['compensation_type'].selection).get(compensation.compensation_type),
                'amount': compensation.amount,
                'state': dict(compensation._fields['state'].selection).get(compensation.state),
                'payment_date': compensation.payment_date,
            }
            data['compensations'].append(compensation_data)
        
        return self._print_report('larr.report_financial_summary', data)
    
    def _print_report(self, report_name, data):
        """Print the report"""
        return {
            'type': 'ir.actions.report',
            'report_name': report_name,
            'report_type': 'qweb-pdf',
            'data': data,
        } 