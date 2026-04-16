# -*- coding: utf-8 -*-
"""
Example Controller: Batch Processing API Endpoint

This demonstrates how to expose parallel batch processing via an API endpoint.
You can customize and integrate this into your existing controllers.

Usage Example:
    POST /api/batch_process
    {
        "file_paths": [
            "/tmp/invoice1.pdf",
            "/tmp/invoice2.pdf",
            "/tmp/invoice3.pdf"
        ],
        "client_id": 1,
        "max_workers": 2
    }

Response:
    {
        "success": true,
        "data": {
            "success_count": 3,
            "fail_count": 0,
            "total": 3,
            "duration_sec": 45.23,
            "speed": 4.0,
            "files": [
                {
                    "filename": "invoice1.pdf",
                    "extraction_id": 123,
                    "status": "done"
                },
                ...
            ]
        }
    }
"""

from odoo import http
from odoo.http import request
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)


class BatchProcessingController(http.Controller):
    """API endpoints for batch document processing."""
    
    @http.route('/api/v1/batch_process_invoices', type='json', auth='user', methods=['POST'])
    def batch_process_invoices(self, **kwargs):
        """
        Process multiple invoice PDFs in parallel.
        
        Request Body (JSON):
            {
                "file_paths": [
                    "/path/to/invoice1.pdf",
                    "/path/to/invoice2.pdf"
                ],
                "client_id": 1,              # Optional: defaults to first client
                "max_workers": 2             # Optional: defaults to system config
            }
        
        Response:
            200 OK:
            {
                "success": true,
                "data": {
                    "success_count": 2,
                    "fail_count": 0,
                    "total": 2,
                    "duration_sec": 45.23,
                    "speed": 4.0,
                    "files": [...]
                }
            }
            
            400 Bad Request:
            {
                "success": false,
                "error": "Error message"
            }
        """
        try:
            # Validate input
            file_paths = kwargs.get('file_paths', [])
            if not file_paths:
                return {
                    'success': False,
                    'error': 'file_paths is required and cannot be empty',
                }
            
            if not isinstance(file_paths, list):
                return {
                    'success': False,
                    'error': 'file_paths must be a list of strings',
                }
            
            # Get client
            client_id = kwargs.get('client_id')
            if client_id:
                client = request.env['purple_ai.client_master'].browse(client_id)
                if not client.exists():
                    return {
                        'success': False,
                        'error': f'Client {client_id} not found',
                    }
            else:
                client = request.env['purple_ai.client_master'].search([], limit=1)
                if not client:
                    return {
                        'success': False,
                        'error': 'No clients configured',
                    }
            
            # Get max_workers
            max_workers = kwargs.get('max_workers')
            if max_workers:
                try:
                    max_workers = int(max_workers)
                except (ValueError, TypeError):
                    max_workers = None
            
            # Prepare file list
            from odoo.addons.purpleai.invoiceai.services.document_processing_service import process_documents_parallel
            
            file_list = []
            for file_path in file_paths:
                if not isinstance(file_path, str):
                    continue
                try:
                    # Verify file exists and is readable
                    path_obj = Path(file_path)
                    if not path_obj.exists():
                        _logger.warning(f"File not found: {file_path}")
                        continue
                    file_list.append((file_path, path_obj.name, None))
                except Exception as e:
                    _logger.error(f"Error processing file path: {file_path} - {str(e)}")
                    continue
            
            if not file_list:
                return {
                    'success': False,
                    'error': 'No valid files found',
                }
            
            # Process files in parallel
            _logger.info(f"Starting batch processing: {len(file_list)} files, {max_workers or 'default'} workers")
            
            if max_workers:
                result = process_documents_parallel(
                    request.env, 
                    client, 
                    file_list, 
                    max_workers=max_workers
                )
            else:
                result = process_documents_parallel(
                    request.env, 
                    client, 
                    file_list
                )
            
            # Format response
            files_data = []
            for extraction_result in result['completed']:
                files_data.append({
                    'filename': extraction_result.file_name,
                    'extraction_id': extraction_result.id,
                    'status': extraction_result.state,
                    'total_amount': extraction_result.invoice_total or 0,
                })
            
            _logger.info(f"Batch processing complete: {result['success_count']} success, {result['fail_count']} failed")
            
            return {
                'success': True,
                'data': {
                    'success_count': result['success_count'],
                    'fail_count': result['fail_count'],
                    'total': result['total'],
                    'duration_sec': round(result['duration_sec'], 2),
                    'speed': round(result['speed'], 1),
                    'files': files_data,
                }
            }
        
        except Exception as e:
            _logger.exception("Error in batch_process_invoices")
            return {
                'success': False,
                'error': str(e),
            }
    
    @http.route('/api/v1/batch_status/<int:batch_id>', type='json', auth='user', methods=['GET'])
    def batch_status(self, batch_id):
        """
        Get status of a batch processing job.
        
        Note: This is a placeholder. You would need to implement 
        batch job tracking in your database.
        """
        return {
            'success': False,
            'error': 'Not implemented - implement batch job tracking',
        }
    
    @http.route('/api/v1/supported_formats', type='json', auth='user', methods=['GET'])
    def supported_formats(self, **kwargs):
        """Get list of supported file formats for batch processing."""
        return {
            'success': True,
            'data': {
                'formats': ['pdf', 'jpg', 'png', 'tiff'],
                'max_workers': 4,
                'timeout_per_file': 600,
                'max_batch_size': 100,
            }
        }


class BatchProcessingWebController(http.Controller):
    """Web UI controllers for batch processing (HTML responses)."""
    
    @http.route('/batch_processor', type='http', auth='user', methods=['GET'])
    def batch_processor_ui(self):
        """Render batch processor UI page."""
        return request.render('purpleai.batch_processor_template', {
            'max_workers_default': 2,
            'clients': request.env['purple_ai.client_master'].search([]),
        })
    
    @http.route('/batch_processor/upload', type='http', auth='user', methods=['POST'])
    def batch_processor_upload(self):
        """Handle file upload for batch processing."""
        try:
            files = request.httprequest.files.getlist('files')
            client_id = int(request.httprequest.form.get('client_id', 0))
            max_workers = int(request.httprequest.form.get('max_workers', 2))
            
            if not files:
                return request.make_response('No files uploaded', 400)
            
            # TODO: Save uploaded files and start batch processing
            # This is a placeholder - implement file storage and processing
            
            return request.make_response('Batch processing started', 202)
        except Exception as e:
            _logger.exception("Error in batch_processor_upload")
            return request.make_response(f'Error: {str(e)}', 500)
