from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
import json
import logging

_logger = logging.getLogger(__name__)


class LARRPortal(CustomerPortal):
    
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        
        if 'larr_project_count' in counters:
            project_count = request.env['larr.project'].search_count([])
            values['larr_project_count'] = project_count
        
        if 'larr_acquisition_count' in counters:
            acquisition_count = request.env['larr.land.acquisition'].search_count([])
            values['larr_acquisition_count'] = acquisition_count
        
        if 'larr_compensation_count' in counters:
            compensation_count = request.env['larr.compensation'].search_count([])
            values['larr_compensation_count'] = compensation_count
        
        return values
    
    @http.route(['/my/larr/projects'], type='http', auth="user", website=True)
    def portal_my_larr_projects(self, **kw):
        values = self._prepare_portal_layout_values()
        projects = request.env['larr.project'].search([])
        values.update({
            'projects': projects,
            'page_name': 'larr_projects',
        })
        return request.render("larr.portal_my_larr_projects", values)
    
    @http.route(['/my/larr/acquisitions'], type='http', auth="user", website=True)
    def portal_my_larr_acquisitions(self, **kw):
        values = self._prepare_portal_layout_values()
        acquisitions = request.env['larr.land.acquisition'].search([])
        values.update({
            'acquisitions': acquisitions,
            'page_name': 'larr_acquisitions',
        })
        return request.render("larr.portal_my_larr_acquisitions", values)
    
    @http.route(['/my/larr/compensations'], type='http', auth="user", website=True)
    def portal_my_larr_compensations(self, **kw):
        values = self._prepare_portal_layout_values()
        compensations = request.env['larr.compensation'].search([])
        values.update({
            'compensations': compensations,
            'page_name': 'larr_compensations',
        })
        return request.render("larr.portal_my_larr_compensations", values)


class LARRController(http.Controller):
    
    @http.route('/larr/api/projects', type='json', auth='user', methods=['GET'])
    def get_projects(self, **kwargs):
        """API endpoint to get LARR projects"""
        try:
            projects = request.env['larr.project'].search([])
            project_data = []
            
            for project in projects:
                project_data.append({
                    'id': project.id,
                    'name': project.name,
                    'code': project.code,
                    'project_type': project.project_type,
                    'state': project.state,
                    'progress_percentage': project.progress_percentage,
                    'total_area_required': project.total_area_required,
                    'estimated_cost': project.estimated_cost,
                })
            
            return {
                'success': True,
                'data': project_data,
                'count': len(project_data)
            }
        except Exception as e:
            _logger.error("Error in get_projects API: %s", str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/larr/api/acquisitions', type='json', auth='user', methods=['GET'])
    def get_acquisitions(self, project_id=None, **kwargs):
        """API endpoint to get land acquisitions"""
        try:
            domain = []
            if project_id:
                domain.append(('project_id', '=', int(project_id)))
            
            acquisitions = request.env['larr.land.acquisition'].search(domain)
            acquisition_data = []
            
            for acquisition in acquisitions:
                acquisition_data.append({
                    'id': acquisition.id,
                    'name': acquisition.name,
                    'project_id': acquisition.project_id.id,
                    'project_name': acquisition.project_id.name,
                    'land_owner': acquisition.land_owner_id.name,
                    'land_area': acquisition.land_area,
                    'land_type': acquisition.land_type,
                    'acquisition_type': acquisition.acquisition_type,
                    'state': acquisition.state,
                    'compensation_amount': acquisition.compensation_amount,
                    'compensation_status': acquisition.compensation_status,
                })
            
            return {
                'success': True,
                'data': acquisition_data,
                'count': len(acquisition_data)
            }
        except Exception as e:
            _logger.error("Error in get_acquisitions API: %s", str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/larr/api/compensations', type='json', auth='user', methods=['GET'])
    def get_compensations(self, acquisition_id=None, **kwargs):
        """API endpoint to get compensations"""
        try:
            domain = []
            if acquisition_id:
                domain.append(('acquisition_id', '=', int(acquisition_id)))
            
            compensations = request.env['larr.compensation'].search(domain)
            compensation_data = []
            
            for compensation in compensations:
                compensation_data.append({
                    'id': compensation.id,
                    'name': compensation.name,
                    'acquisition_id': compensation.acquisition_id.id,
                    'acquisition_name': compensation.acquisition_id.name,
                    'beneficiary': compensation.beneficiary_id.name,
                    'compensation_type': compensation.compensation_type,
                    'amount': compensation.amount,
                    'state': compensation.state,
                    'payment_method': compensation.payment_method,
                    'payment_date': compensation.payment_date.isoformat() if compensation.payment_date else None,
                })
            
            return {
                'success': True,
                'data': compensation_data,
                'count': len(compensation_data)
            }
        except Exception as e:
            _logger.error("Error in get_compensations API: %s", str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/larr/api/dashboard', type='json', auth='user', methods=['GET'])
    def get_dashboard_data(self, **kwargs):
        """API endpoint to get dashboard data"""
        try:
            dashboard = request.env['larr.dashboard'].search([])
            if dashboard:
                dashboard = dashboard[0]
                return {
                    'success': True,
                    'data': {
                        'project_count': dashboard.project_count,
                        'active_project_count': dashboard.active_project_count,
                        'completed_project_count': dashboard.completed_project_count,
                        'acquisition_count': dashboard.acquisition_count,
                        'pending_acquisition_count': dashboard.pending_acquisition_count,
                        'completed_acquisition_count': dashboard.completed_acquisition_count,
                        'rehabilitation_count': dashboard.rehabilitation_count,
                        'pending_rehabilitation_count': dashboard.pending_rehabilitation_count,
                        'completed_rehabilitation_count': dashboard.completed_rehabilitation_count,
                        'compensation_count': dashboard.compensation_count,
                        'pending_compensation_count': dashboard.pending_compensation_count,
                        'paid_compensation_count': dashboard.paid_compensation_count,
                        'stakeholder_count': dashboard.stakeholder_count,
                        'active_stakeholder_count': dashboard.active_stakeholder_count,
                        'total_area_acquired': dashboard.total_area_acquired,
                        'total_compensation_amount': dashboard.total_compensation_amount,
                    }
                }
            else:
                return {
                    'success': True,
                    'data': {
                        'project_count': 0,
                        'active_project_count': 0,
                        'completed_project_count': 0,
                        'acquisition_count': 0,
                        'pending_acquisition_count': 0,
                        'completed_acquisition_count': 0,
                        'rehabilitation_count': 0,
                        'pending_rehabilitation_count': 0,
                        'completed_rehabilitation_count': 0,
                        'compensation_count': 0,
                        'pending_compensation_count': 0,
                        'paid_compensation_count': 0,
                        'stakeholder_count': 0,
                        'active_stakeholder_count': 0,
                        'total_area_acquired': 0.0,
                        'total_compensation_amount': 0.0,
                    }
                }
        except Exception as e:
            _logger.error("Error in get_dashboard_data API: %s", str(e))
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/larr/api/project/<int:project_id>/dashboard', type='json', auth='user', methods=['GET'])
    def get_project_dashboard(self, project_id, **kwargs):
        """API endpoint to get project-specific dashboard data"""
        try:
            project_dashboard = request.env['larr.project.dashboard'].search([('project_id', '=', project_id)])
            if project_dashboard:
                dashboard = project_dashboard[0]
                return {
                    'success': True,
                    'data': {
                        'project_name': dashboard.project_name,
                        'project_code': dashboard.project_code,
                        'project_type': dashboard.project_type,
                        'acquisition_count': dashboard.acquisition_count,
                        'completed_acquisition_count': dashboard.completed_acquisition_count,
                        'acquisition_progress': dashboard.acquisition_progress,
                        'rehabilitation_count': dashboard.rehabilitation_count,
                        'completed_rehabilitation_count': dashboard.completed_rehabilitation_count,
                        'rehabilitation_progress': dashboard.rehabilitation_progress,
                        'compensation_count': dashboard.compensation_count,
                        'paid_compensation_count': dashboard.paid_compensation_count,
                        'compensation_progress': dashboard.compensation_progress,
                        'total_area_acquired': dashboard.total_area_acquired,
                        'total_compensation_amount': dashboard.total_compensation_amount,
                    }
                }
            else:
                return {
                    'success': False,
                    'error': 'Project dashboard not found'
                }
        except Exception as e:
            _logger.error("Error in get_project_dashboard API: %s", str(e))
            return {
                'success': False,
                'error': str(e)
            } 