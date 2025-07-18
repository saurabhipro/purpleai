from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import sql
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class LARRDashboard(models.Model):
    _name = 'larr.dashboard'
    _description = 'LARR Dashboard'
    _auto = False

    name = fields.Char('Name')
    project_count = fields.Integer('Total Projects')
    active_project_count = fields.Integer('Active Projects')
    completed_project_count = fields.Integer('Completed Projects')
    
    acquisition_count = fields.Integer('Total Acquisitions')
    pending_acquisition_count = fields.Integer('Pending Acquisitions')
    completed_acquisition_count = fields.Integer('Completed Acquisitions')
    
    rehabilitation_count = fields.Integer('Total Rehabilitations')
    pending_rehabilitation_count = fields.Integer('Pending Rehabilitations')
    completed_rehabilitation_count = fields.Integer('Completed Rehabilitations')
    
    compensation_count = fields.Integer('Total Compensations')
    pending_compensation_count = fields.Integer('Pending Compensations')
    paid_compensation_count = fields.Integer('Paid Compensations')
    
    stakeholder_count = fields.Integer('Total Stakeholders')
    active_stakeholder_count = fields.Integer('Active Stakeholders')
    
    total_area_acquired = fields.Float('Total Area Acquired (Acres)')
    total_compensation_amount = fields.Monetary('Total Compensation Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    def init(self):
        sql.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE or REPLACE VIEW %s as (
                SELECT 
                    1 as id,
                    'LARR Dashboard' as name,
                    (SELECT COUNT(*) FROM larr_project) as project_count,
                    (SELECT COUNT(*) FROM larr_project WHERE state = 'active') as active_project_count,
                    (SELECT COUNT(*) FROM larr_project WHERE state = 'completed') as completed_project_count,
                    (SELECT COUNT(*) FROM larr_land_acquisition) as acquisition_count,
                    (SELECT COUNT(*) FROM larr_land_acquisition WHERE state IN ('draft', 'survey', 'negotiation')) as pending_acquisition_count,
                    (SELECT COUNT(*) FROM larr_land_acquisition WHERE state = 'completed') as completed_acquisition_count,
                    (SELECT COUNT(*) FROM larr_rehabilitation) as rehabilitation_count,
                    (SELECT COUNT(*) FROM larr_rehabilitation WHERE state IN ('draft', 'survey', 'planning', 'implementation')) as pending_rehabilitation_count,
                    (SELECT COUNT(*) FROM larr_rehabilitation WHERE state = 'completed') as completed_rehabilitation_count,
                    (SELECT COUNT(*) FROM larr_compensation) as compensation_count,
                    (SELECT COUNT(*) FROM larr_compensation WHERE state IN ('draft', 'approved')) as pending_compensation_count,
                    (SELECT COUNT(*) FROM larr_compensation WHERE state = 'paid') as paid_compensation_count,
                    (SELECT COUNT(*) FROM larr_stakeholder) as stakeholder_count,
                    (SELECT COUNT(*) FROM larr_stakeholder WHERE state = 'active') as active_stakeholder_count,
                    (SELECT COALESCE(SUM(land_area), 0) FROM larr_land_acquisition WHERE state = 'completed') as total_area_acquired,
                    (SELECT COALESCE(SUM(amount), 0) FROM larr_compensation WHERE state = 'paid') as total_compensation_amount
            )
        """ % self._table)


class LARRProjectDashboard(models.Model):
    _name = 'larr.project.dashboard'
    _description = 'LARR Project Dashboard'
    _auto = False

    project_id = fields.Many2one('larr.project', 'Project')
    project_name = fields.Char('Project Name')
    project_code = fields.Char('Project Code')
    project_type = fields.Selection([
        ('infrastructure', 'Infrastructure'),
        ('industrial', 'Industrial'),
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('agricultural', 'Agricultural'),
        ('other', 'Other')
    ], string='Project Type')
    
    acquisition_count = fields.Integer('Total Acquisitions')
    completed_acquisition_count = fields.Integer('Completed Acquisitions')
    acquisition_progress = fields.Float('Acquisition Progress %')
    
    rehabilitation_count = fields.Integer('Total Rehabilitations')
    completed_rehabilitation_count = fields.Integer('Completed Rehabilitations')
    rehabilitation_progress = fields.Float('Rehabilitation Progress %')
    
    compensation_count = fields.Integer('Total Compensations')
    paid_compensation_count = fields.Integer('Paid Compensations')
    compensation_progress = fields.Float('Compensation Progress %')
    
    total_area_acquired = fields.Float('Total Area Acquired (Acres)')
    total_compensation_amount = fields.Monetary('Total Compensation Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    def init(self):
        sql.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE or REPLACE VIEW %s as (
                SELECT 
                    p.id as id,
                    p.id as project_id,
                    p.name as project_name,
                    p.code as project_code,
                    p.project_type,
                    (SELECT COUNT(*) FROM larr_land_acquisition la WHERE la.project_id = p.id) as acquisition_count,
                    (SELECT COUNT(*) FROM larr_land_acquisition la WHERE la.project_id = p.id AND la.state = 'completed') as completed_acquisition_count,
                    CASE 
                        WHEN (SELECT COUNT(*) FROM larr_land_acquisition la WHERE la.project_id = p.id) > 0 
                        THEN (SELECT COUNT(*) FROM larr_land_acquisition la WHERE la.project_id = p.id AND la.state = 'completed') * 100.0 / (SELECT COUNT(*) FROM larr_land_acquisition la WHERE la.project_id = p.id)
                        ELSE 0 
                    END as acquisition_progress,
                    (SELECT COUNT(*) FROM larr_rehabilitation r WHERE r.project_id = p.id) as rehabilitation_count,
                    (SELECT COUNT(*) FROM larr_rehabilitation r WHERE r.project_id = p.id AND r.state = 'completed') as completed_rehabilitation_count,
                    CASE 
                        WHEN (SELECT COUNT(*) FROM larr_rehabilitation r WHERE r.project_id = p.id) > 0 
                        THEN (SELECT COUNT(*) FROM larr_rehabilitation r WHERE r.project_id = p.id AND r.state = 'completed') * 100.0 / (SELECT COUNT(*) FROM larr_rehabilitation r WHERE r.project_id = p.id)
                        ELSE 0 
                    END as rehabilitation_progress,
                    (SELECT COUNT(*) FROM larr_compensation c JOIN larr_land_acquisition la ON c.acquisition_id = la.id WHERE la.project_id = p.id) as compensation_count,
                    (SELECT COUNT(*) FROM larr_compensation c JOIN larr_land_acquisition la ON c.acquisition_id = la.id WHERE la.project_id = p.id AND c.state = 'paid') as paid_compensation_count,
                    CASE 
                        WHEN (SELECT COUNT(*) FROM larr_compensation c JOIN larr_land_acquisition la ON c.acquisition_id = la.id WHERE la.project_id = p.id) > 0 
                        THEN (SELECT COUNT(*) FROM larr_compensation c JOIN larr_land_acquisition la ON c.acquisition_id = la.id WHERE la.project_id = p.id AND c.state = 'paid') * 100.0 / (SELECT COUNT(*) FROM larr_compensation c JOIN larr_land_acquisition la ON c.acquisition_id = la.id WHERE la.project_id = p.id)
                        ELSE 0 
                    END as compensation_progress,
                    (SELECT COALESCE(SUM(la.land_area), 0) FROM larr_land_acquisition la WHERE la.project_id = p.id AND la.state = 'completed') as total_area_acquired,
                    (SELECT COALESCE(SUM(c.amount), 0) FROM larr_compensation c JOIN larr_land_acquisition la ON c.acquisition_id = la.id WHERE la.project_id = p.id AND c.state = 'paid') as total_compensation_amount
                FROM larr_project p
            )
        """ % self._table) 