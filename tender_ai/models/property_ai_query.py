# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging
from ..services.sql_query_service import generate_sql_from_query, execute_ai_sql

_logger = logging.getLogger(__name__)

class PropertyAIQuery(models.Model):
    _name = 'tende_ai.property_ai_query'
    _description = 'Property AI Semantic Query'
    _order = 'create_date desc'

    name = fields.Char(string='Query Topic', required=True, default="Property Analysis")
    question = fields.Char(string='Ask AI anything about Properties', required=True, 
                          placeholder="e.g. Total properties with solar in Ward 10?")
    
    generated_sql = fields.Text(string='Generated SQL', readonly=True)
    execution_time = fields.Float(string='Execution Time (s)', readonly=True)
    
    result_count = fields.Integer(string='Results Found', readonly=True)
    results_html = fields.Html(string='AI Analysis Result')
    
    raw_results = fields.Text(string='Raw JSON Results', readonly=True)

    def action_check_models(self):
        """Debug method to show available models for the current key."""
        from ..services.gemini_service import list_available_models
        models = list_available_models(env=self.env)
        if not models:
            msg = "Could not retrieve models. Check your API key."
        else:
            msg = f"Available Models for your Key:\n" + "\n".join(models)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'AI Model Check',
                'message': msg,
                'sticky': True,
            }
        }

    def action_run_query(self):
        self.ensure_one()
        if not self.question:
            return

        # 1. Generate SQL
        # We include related models so AI understands Joins (Survey, Zone, Ward, etc.)
        property_models = [
            'ddn.property.info', 
            'ddn.property.survey', 
            'ddn.property.type',
            'ddn.property.group'
        ]
        sql, error = generate_sql_from_query(self.env, property_models, self.question)
        if error:
            self.results_html = f"<div class='alert alert-danger'>{error}</div>"
            return

        self.generated_sql = sql

        # 2. Execute SQL
        import time
        start_time = time.time()
        results, exec_error = execute_ai_sql(self.env, sql)
        self.execution_time = time.time() - start_time

        if exec_error:
            self.results_html = f"<div class='alert alert-warning'><b>SQL Error:</b> {exec_error}</div>"
            return

        self.result_count = len(results)
        self.raw_results = str(results)

        # 3. Format Results into HTML Table
        if not results:
            self.results_html = "<div class='alert alert-info'>No records found matching your criteria.</div>"
            return

        headers = results[0].keys()
        html = '<table class="table table-sm table-bordered mt-3"><thead><tr class="bg-light">'
        for h in headers:
            html += f'<th>{h}</th>'
        html += '</tr></thead><tbody>'
        
        for row in results[:50]: # Limit to 50 for UI
            html += '<tr>'
            for val in row.values():
                html += f'<td>{val}</td>'
            html += '</tr>'
        
        if len(results) > 50:
            html += f'<tr><td colspan="{len(headers)}" class="text-center text-muted">... showing first 50 of {len(results)} records ...</td></tr>'
        
        html += '</tbody></table>'
        
        # 4. Final summarization prompt (Optional)
        self.results_html = html
