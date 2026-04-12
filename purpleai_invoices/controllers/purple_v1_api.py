# -*- coding: utf-8 -*-
import json
import logging
import base64
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PurpleInvoicesAPI(http.Controller):
    def _api_auth(self):
        """Allow Odoo browser session or X-AI-Core-Dev-Key (when that key is set in AI Core).

        Returns (ok: bool, reason: str|None) reason in {None, 'missing_header', 'mismatch'}.
        """
        if request.session.uid:
            return True, None
        icp = request.env['ir.config_parameter'].sudo()
        expected = str(icp.get_param('ai_core.react_dev_api_key') or '').strip()
        raw = request.httprequest.headers.get('X-AI-Core-Dev-Key')
        header = str(raw or '').strip()
        if not expected:
            return True, None
        if not header:
            _logger.info('Purple Invoices API: dev key required but X-AI-Core-Dev-Key header missing')
            return False, 'missing_header'
        if header != expected:
            _logger.info('Purple Invoices API: dev key mismatch (header present, length=%s)', len(header))
            return False, 'mismatch'
        return True, None

    def _cors_headers(self):
        # Delegate to ai_core's shared cors logic if possible, or define locally
        return [
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
            ('Access-Control-Allow-Headers', 'Content-Type, X-AI-Core-Dev-Key'),
        ]

    def _json_response(self, data, status=200):
        body = json.dumps(data)
        headers = [('Content-Type', 'application/json')] + self._cors_headers()
        return request.make_response(body, headers=headers, status=status)

    def _get_upload_file(self):
        """Resolve uploaded file from multipart form (common field names)."""
        files = request.httprequest.files
        for key in ('file', 'upload', 'attachment', 'document'):
            f = files.get(key)
            if f and getattr(f, 'filename', None):
                return f
        if files:
            first = next(iter(files.values()), None)
            if first and getattr(first, 'filename', None):
                return first
        _logger.info('Purple upload: no usable file; multipart keys=%s', list(files.keys()))
        return None

    def _resolve_client(self):
        """Pick client from form client_id or first available.

        Returns (client_recordset, error_code) where error_code is None or
        'bad_client_id' / 'unknown_client_id'.
        """
        Client = request.env['purple_ai.client'].sudo()
        raw_id = request.httprequest.form.get('client_id')
        if raw_id is not None and str(raw_id).strip() != '':
            try:
                cid = int(raw_id)
            except (TypeError, ValueError):
                return Client.browse(), 'bad_client_id'
            client = Client.browse(cid)
            if client.exists():
                return client, None
            return Client.browse(), 'unknown_client_id'
        return Client.search([], limit=1), None

    @http.route('/purple_invoices/v1/ping', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def ping(self, **_kwargs):
        if request.httprequest.method == 'OPTIONS':
            return request.make_response('', headers=self._cors_headers(), status=204)
        return self._json_response({'ok': True, 'module': 'purpleai_invoices'})

    @http.route(
        ['/purple_invoices/v1/clients', '/purple_invoices/v1/clients/'],
        type='http',
        auth='none',
        methods=['GET', 'OPTIONS'],
        csrf=False,
    )
    def clients_list(self, **_kwargs):
        if request.httprequest.method == 'OPTIONS':
            return request.make_response('', headers=self._cors_headers(), status=204)
        ok, reason = self._api_auth()
        if not ok:
            return self._json_response(
                {
                    'ok': False,
                    'error': 'Unauthorized',
                    'reason': reason,
                    'hint': 'Log in to Odoo in this browser, or send X-AI-Core-Dev-Key matching AI Core → React UI Dev API Key.',
                },
                status=401,
            )
        clients = request.env['purple_ai.client'].sudo().search([], order='id')
        payload = [
            {'id': c.id, 'name': c.name, 'extraction_master_id': c.extraction_master_id.id}
            for c in clients
        ]
        return self._json_response({'ok': True, 'clients': payload, 'count': len(payload)})

    @http.route('/purple_invoices/v1/upload', type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False)
    def upload(self, **_kwargs):
        if request.httprequest.method == 'OPTIONS':
            return request.make_response('', headers=self._cors_headers(), status=204)
        
        ok, reason = self._api_auth()
        if not ok:
            return self._json_response(
                {
                    'ok': False,
                    'error': 'Unauthorized',
                    'reason': reason,
                    'hint': 'Use the exact same value as Settings → General Settings → AI Core → '
                    'React UI Dev API Key (save Odoo after changing). Clear that field and save '
                    'to turn off API key checks.',
                },
                status=401,
            )

        _logger.warning(
            'Purple upload POST: content_type=%r content_length=%r file_keys=%s form_keys=%s',
            request.httprequest.content_type,
            request.httprequest.content_length,
            list(request.httprequest.files.keys()),
            list(request.httprequest.form.keys()),
        )

        uploaded_file = self._get_upload_file()
        if not uploaded_file:
            _logger.warning(
                'Purple upload → 400 no_file (multipart had no usable part). '
                'If file_keys is empty, the proxy may be stripping multipart or Content-Type is wrong.'
            )
            return self._json_response(
                {
                    'ok': False,
                    'error': 'No file uploaded',
                    'reason': 'no_file',
                    'hint': 'POST multipart form must include a file field named "file" (or upload/attachment).',
                },
                status=400,
            )

        client, client_err = self._resolve_client()
        if client_err == 'bad_client_id':
            return self._json_response(
                {
                    'ok': False,
                    'error': 'Invalid client_id',
                    'reason': 'bad_client_id',
                    'hint': 'Form field client_id must be an integer.',
                },
                status=400,
            )
        if client_err == 'unknown_client_id':
            return self._json_response(
                {
                    'ok': False,
                    'error': 'Unknown client_id',
                    'reason': 'unknown_client_id',
                    'hint': 'No purple_ai.client with that id. Create one under Purple Invoices → Client Master.',
                },
                status=400,
            )
        if not client:
            n = request.env['purple_ai.client'].sudo().search_count([])
            _logger.warning(
                'Purple upload → 400 no_client (purple_ai.client count=%s). '
                'Create a client under Purple Invoices → Client Master.',
                n,
            )
            return self._json_response(
                {
                    'ok': False,
                    'error': 'No client configured in Odoo',
                    'reason': 'no_client',
                    'hint': 'In Odoo open Purple Invoices → Client Master (or Clients): create a client with '
                    'an Extraction Template. Set Root Folder Path in Purple Invoices settings if required. '
                    'Optional: send form field client_id=<id> to choose a specific client.',
                },
                status=400,
            )

        content = uploaded_file.read()
        filename = uploaded_file.filename

        try:
            # Create extraction record
            res_rec = request.env['purple_ai.extraction_result'].sudo().create({
                'client_id': client.id,
                'filename': filename,
                'pdf_file': base64.b64encode(content),
                'pdf_filename': filename,
                'state': 'processing',
            })
            
            # Commit so background job can see it
            request.env.cr.commit()
            
            # Start background processing (retry logic handles the call)
            res_rec.action_retry_extraction()

            return self._json_response({
                'ok': True, 
                'res_id': res_rec.id,
                'filename': filename,
                'state': 'processing'
            })
        except Exception as e:
            _logger.exception("Upload failed")
            return self._json_response({'ok': False, 'error': str(e)}, status=500)

    @http.route('/purple_invoices/v1/results', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def results(self, **_kwargs):
        if request.httprequest.method == 'OPTIONS':
            return request.make_response('', headers=self._cors_headers(), status=204)
        
        ok, reason = self._api_auth()
        if not ok:
            return self._json_response(
                {
                    'ok': False,
                    'error': 'Unauthorized',
                    'reason': reason,
                    'hint': 'Use the exact same value as Settings → General Settings → AI Core → '
                    'React UI Dev API Key (save Odoo after changing). Clear that field and save '
                    'to turn off API key checks.',
                },
                status=401,
            )

        records = request.env['purple_ai.extraction_result'].sudo().search([], limit=20, order='create_date desc')
        data = []
        for r in records:
            data.append({
                'id': r.id,
                'name': r.filename,
                'status': r.state,
                'date': r.create_date.strftime('%Y-%m-%d %H:%M'),
                'has_data': bool(r.extracted_data),
            })
        return self._json_response({'ok': True, 'results': data})

    @http.route('/purple_invoices/v1/viewer_data/<int:res_id>', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def viewer_data(self, res_id, **_kwargs):
        if request.httprequest.method == 'OPTIONS':
            return request.make_response('', headers=self._cors_headers(), status=204)
        
        ok, reason = self._api_auth()
        if not ok:
            return self._json_response(
                {
                    'ok': False,
                    'error': 'Unauthorized',
                    'reason': reason,
                    'hint': 'Use the exact same value as Settings → General Settings → AI Core → '
                    'React UI Dev API Key (save Odoo after changing). Clear that field and save '
                    'to turn off API key checks.',
                },
                status=401,
            )

        rec = request.env['purple_ai.extraction_result'].sudo().browse(res_id)
        if not rec.exists():
            return self._json_response({'ok': False, 'error': 'Record not found'}, status=404)

        # Return file as base64 and the extraction JSON
        return self._json_response({
            'ok': True,
            'filename': rec.filename,
            'pdf_base64': rec.pdf_file.decode('utf-8') if rec.pdf_file else '',
            'extracted_json': json.loads(rec.extracted_data) if rec.extracted_data else {},
            'status': rec.state
        })
