# -*- coding: utf-8 -*-

import json
import base64
import os
from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class TenderAPIController(http.Controller):

    @http.route('/api/tender/upload', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_tender_zip(self, **kwargs):
        """
        POST /api/tender/upload
        Accepts multipart/form-data with 'zip_file' field
        
        Returns JSON with job_id and status
        """
        try:
            if 'zip_file' not in request.httprequest.files:
                return request.make_response(
                    json.dumps({'error': 'zip_file is required (multipart/form-data)'}),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )

            uploaded_file = request.httprequest.files['zip_file']
            
            # Read file content
            zip_content = uploaded_file.read()
            zip_filename = uploaded_file.filename

            # Create tender job
            job = request.env['tende_ai.job'].create({
                'zip_file': base64.b64encode(zip_content),
                'zip_filename': zip_filename,
                'state': 'draft',
            })

            # Start processing
            job.action_process_zip()

            return request.make_response(
                json.dumps({
                    'message': 'Tender accepted ✅. Processing started. Please check after some minutes.',
                    'job_id': job.name,
                    'status': 'processing',
                    'status_check': f'/api/tender/status?job_id={job.name}',
                }),
                headers=[('Content-Type', 'application/json')],
                status=200
            )

        except Exception as e:
            _logger.error(f"Error uploading tender ZIP: {str(e)}", exc_info=True)
            return request.make_response(
                json.dumps({'error': str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

    @http.route('/api/tender/status', type='http', auth='user', methods=['GET'], csrf=False)
    def get_tender_status(self, job_id=None, **kwargs):
        """
        GET /api/tender/status?job_id=TENDER_01
        
        Returns JSON with job status and details
        """
        try:
            if not job_id:
                return request.make_response(
                    json.dumps({'error': 'job_id parameter is required'}),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )

            job = request.env['tende_ai.job'].search([('name', '=', job_id)], limit=1)
            
            if not job:
                return request.make_response(
                    json.dumps({'error': f'Job {job_id} not found'}),
                    headers=[('Content-Type', 'application/json')],
                    status=404
                )

            # Build response
            response_data = {
                'job_id': job.name,
                'status': job.state,
                'tender_reference': job.tender_reference or '',
                'tender_description': job.tender_description or '',
                'companies_detected': job.companies_detected,
                'error_message': job.error_message or '',
            }

            # Add tender details if available
            if job.tender_id:
                response_data['tender'] = {
                    'tender_id': job.tender_id.tender_id or '',
                    'ref_no': job.tender_id.ref_no or '',
                    'department_name': job.tender_id.department_name or '',
                }

            # Add analytics if available
            if job.analytics:
                try:
                    response_data['analytics'] = json.loads(job.analytics)
                except Exception:
                    response_data['analytics'] = {}

            # Add counts
            response_data['bidders_count'] = len(job.bidders)
            response_data['eligibility_criteria_count'] = len(job.eligibility_criteria)

            return request.make_response(
                json.dumps(response_data),
                headers=[('Content-Type', 'application/json')],
                status=200
            )

        except Exception as e:
            _logger.error(f"Error getting tender status: {str(e)}", exc_info=True)
            return request.make_response(
                json.dumps({'error': str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

    @http.route('/api/tender/list', type='http', auth='user', methods=['GET'], csrf=False)
    def list_tenders(self, **kwargs):
        """
        GET /api/tender/list
        
        Returns JSON list of all tender jobs (latest first)
        """
        try:
            jobs = request.env['tende_ai.job'].search([], order='create_date desc', limit=100)
            
            jobs_list = []
            for job in jobs:
                jobs_list.append({
                    'job_id': job.name,
                    'status': job.state,
                    'tender_reference': job.tender_reference or '',
                    'companies_detected': job.companies_detected,
                    'create_date': job.create_date.isoformat() if job.create_date else '',
                })

            return request.make_response(
                json.dumps({'jobs': jobs_list}),
                headers=[('Content-Type', 'application/json')],
                status=200
            )

        except Exception as e:
            _logger.error(f"Error listing tenders: {str(e)}", exc_info=True)
            return request.make_response(
                json.dumps({'error': str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

    @http.route('/api/tender/chat', type='http', auth='user', methods=['POST'], csrf=False)
    def chat_about_job(self, **kwargs):
        """
        POST /api/tender/chat
        Body JSON:
          - job_id: job name (e.g. TENDER_01) OR integer record id
          - question: required
          - history: optional list of {role, content}
          - model: optional (gemini model)
          - persist: optional bool (post Q&A into chatter)
        """
        try:
            data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
            job_id = data.get('job_id')
            question = (data.get('question') or '').strip()
            history = data.get('history')
            model = data.get('model')
            persist = bool(data.get('persist') or False)

            if not job_id:
                return request.make_response(
                    json.dumps({'success': False, 'error': 'job_id is required'}),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )
            if not question:
                return request.make_response(
                    json.dumps({'success': False, 'error': 'question is required'}),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )

            # job_id can be either numeric record id or the job "name" (sequence)
            job = None
            if isinstance(job_id, int) or (isinstance(job_id, str) and job_id.isdigit()):
                job = request.env['tende_ai.job'].sudo().browse(int(job_id))
            if not job or not job.exists():
                job = request.env['tende_ai.job'].sudo().search([('name', '=', str(job_id))], limit=1)
            if not job:
                return request.make_response(
                    json.dumps({'success': False, 'error': f'Job {job_id} not found'}),
                    headers=[('Content-Type', 'application/json')],
                    status=404
                )

            from ..services.tender_chat_service import answer_job_question, post_chat_to_job_chatter

            res = answer_job_question(
                env=request.env,
                job_id=job.id,
                question=question,
                history=history,
                model=model,
            ) or {}

            if persist and res.get('success') and res.get('answer'):
                post_chat_to_job_chatter(request.env, job_id=job.id, question=question, answer=res.get('answer'))

            status = int(res.pop('status', 200) or 200)
            return request.make_response(
                json.dumps(res),
                headers=[('Content-Type', 'application/json')],
                status=status
            )

        except Exception as e:
            _logger.error(f"Error in tender chat: {str(e)}", exc_info=True)
            return request.make_response(
                json.dumps({'success': False, 'error': str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

