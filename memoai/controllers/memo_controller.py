# -*- coding: utf-8 -*-
import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MemoAIController(http.Controller):

    @http.route('/memo_ai/run_step', type='json', auth='user', methods=['POST'])
    def run_step(self, session_id, step, **kwargs):
        """
        AJAX endpoint called by the OWL workflow component to trigger each step.
        Returns {success, output, state, error}.
        """
        session = request.env['memo_ai.session'].browse(int(session_id))
        if not session.exists():
            return {'success': False, 'error': 'Session not found'}

        try:
            if step == 1:
                session.action_run_step1()
                return {'success': True, 'output': session.step1_output, 'state': session.state}
            elif step == 2:
                session.action_run_step2()
                return {'success': True, 'output': session.step2_output, 'state': session.state}
            elif step == 3:
                session.action_run_step3()
                return {'success': True, 'output': session.step3_output, 'state': session.state}
            elif step == 4:
                session.action_run_step4()
                return {'success': True, 'output': session.step4_output, 'state': session.state}
            else:
                return {'success': False, 'error': f'Unknown step: {step}'}
        except Exception as e:
            _logger.error("MemoAI step %s failed for session %s: %s", step, session_id, str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/memo_ai/save_step_output', type='json', auth='user', methods=['POST'])
    def save_step_output(self, session_id, step, output, **kwargs):
        """Save user-edited output for a specific step."""
        session = request.env['memo_ai.session'].browse(int(session_id))
        if not session.exists():
            return {'success': False, 'error': 'Session not found'}
        field_map = {
            1: 'step1_output',
            2: 'step2_output',
            3: 'step3_output',
            4: 'step4_output',
        }
        field = field_map.get(int(step))
        if not field:
            return {'success': False, 'error': 'Invalid step'}
        session.write({field: output})
        return {'success': True}
