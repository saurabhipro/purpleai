# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class WordAddinController(http.Controller):

    @http.route('/word_addin/manifest.xml', type='http', auth='none', methods=['GET'], cors='*')
    def get_manifest(self, **kwargs):
        """Serve a static manifest.xml for Word Add-in."""
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        
        manifest = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<OfficeApp 
          xmlns="http://schemas.microsoft.com/office/appforoffice/1.1" 
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
          xmlns:bt="http://schemas.microsoft.com/office/officeappbasictypes/1.0" 
          xmlns:ov="http://schemas.microsoft.com/office/taskpaneappversionoverrides" 
          xsi:type="TaskPaneApp">
  <Id>54f67c00-d38e-4a4f-ba7b-663f707f1234</Id>
  <Version>1.5.0.0</Version>
  <ProviderName>Purple AI</ProviderName>
  <DefaultLocale>en-US</DefaultLocale>
  <DisplayName DefaultValue="Memo AI Editor" />
  <Description DefaultValue="Edit AI Analysis Memos in Word" />
  <IconUrl DefaultValue="{base_url}/word_addin/static/src/img/icon-32.png" />
  <HighResolutionIconUrl DefaultValue="{base_url}/word_addin/static/src/img/icon-64.png" />
  <AppDomains><AppDomain>{base_url}</AppDomain></AppDomains>
  <Hosts><Host Name="Document" /></Hosts>
  <DefaultSettings><SourceLocation DefaultValue="{base_url}/word_addin/taskpane" /></DefaultSettings>
  <Permissions>ReadWriteDocument</Permissions>
  <VersionOverrides xmlns="http://schemas.microsoft.com/office/taskpaneappversionoverrides" xsi:type="VersionOverrideV1_0">
    <Hosts>
      <Host xsi:type="Document">
        <DesktopFormFactor>
          <FunctionFile resid="Commands.Url" />
          <ExtensionPoint xsi:type="PrimaryCommandSurface">
            <OfficeTab id="TabHome">
              <Group id="MemoGroup">
                <Label DefaultValue="Memo AI" />
                <Control xsi:type="Button" id="MemoButton">
                  <Label DefaultValue="Open Editor" />
                  <Icon><bt:Image size="32" resid="Icon.32x32" /></Icon>
                  <Action xsi:type="ShowTaskpane">
                    <TaskpaneId>MemoTaskpane</TaskpaneId>
                    <SourceLocation resid="Taskpane.Url" />
                  </Action>
                </Control>
              </Group>
            </OfficeTab>
          </ExtensionPoint>
        </DesktopFormFactor>
      </Host>
    </Hosts>
    <Resources>
      <bt:Images>
        <bt:Image id="Icon.32x32" DefaultValue="{base_url}/word_addin/static/src/img/icon-32.png" />
      </bt:Images>
      <bt:Urls>
        <bt:Url id="Commands.Url" DefaultValue="{base_url}/word_addin/static/src/html/commands.html" />
        <bt:Url id="Taskpane.Url" DefaultValue="{base_url}/word_addin/taskpane" />
      </bt:Urls>
    </Resources>
  </VersionOverrides>
</OfficeApp>
"""
        headers = [
            ('Content-Type', 'text/xml'),
            ('Content-Disposition', 'attachment; filename="manifest.xml"'),
            ('Access-Control-Allow-Origin', '*'),
        ]
        return request.make_response(manifest, headers)

    @http.route(['/word_addin/taskpane'], type='http', auth='none', methods=['GET'], website=False)
    def render_taskpane(self, **kwargs):
        """Render the main taskpane page."""
        session_id = kwargs.get('session_id') or request.session.get('active_memo_session_id')
        step_num = kwargs.get('step_num') or request.session.get('active_memo_session_step') or 'all'
        
        return request.render('word_addin.taskpane_template', {
            'session_id': session_id,
            'step_num': step_num,
        })

    @http.route('/word_addin/get_memo_data', type='json', auth='none', methods=['POST'], cors='*', csrf=False)
    def get_memo_data(self, session_id=None, step_num='all'):
        """Fetch data with CSRF disabled for cross-app compatibility."""
        if not request.session.uid:
            return {'error': 'authentication_required'}

        if not session_id:
            session_id = request.session.get('active_memo_session_id')
        if not step_num:
            step_num = request.session.get('active_memo_session_step') or 'all'

        if not session_id:
            return {'error': 'no_active_session'}

        session = request.env['memo_ai.session'].sudo().browse(int(session_id))
        if not session.exists():
            return {'error': 'session_not_found'}

        steps = []
        if step_num == 'all':
            steps = [
                {'id': 1, 'title': 'Step 1: Core Issues', 'content': session.step1_output_html},
                {'id': 2, 'title': 'Step 2: Legal Analysis', 'content': session.step2_output_html},
                {'id': 3, 'title': 'Step 3: Risk Assessment', 'content': session.step3_output_html},
                {'id': 4, 'title': 'Step 4: Final Recommendation', 'content': session.step4_output_html},
            ]
        else:
            step_attr = f"step{step_num}_output_html"
            steps = [{
                'id': int(step_num),
                'title': f"Step {step_num}",
                'content': getattr(session, step_attr, '')
            }]

        return {
            'name': session.name,
            'subject': session.subject_id.name if session.subject_id else 'General Analysis',
            'steps': steps
        }

    @http.route('/word_addin/get_recent_sessions', type='json', auth='none', methods=['POST'], cors='*', csrf=False)
    def get_recent_sessions(self, **kwargs):
        """Return 5 recent sessions with CSRF disabled."""
        if not request.session.uid:
            return {'error': 'authentication_required'}

        sessions = request.env['memo_ai.session'].sudo().search([
            ('create_uid', '=', request.session.uid)
        ], limit=5, order='write_date desc')
        
        return [{
            'id': s.id,
            'name': s.name,
            'subject': s.subject_id.name if s.subject_id else 'Generic',
            'date': s.write_date.strftime('%Y-%m-%d')
        } for s in sessions]

    @http.route('/word_addin/save_memo_data', type='json', auth='none', methods=['POST'], cors='*', csrf=False)
    def save_memo_data(self, session_id, steps_data):
        """Save data with CSRF disabled."""
        if not request.session.uid:
            return {'error': 'authentication_required'}

        session = request.env['memo_ai.session'].sudo().browse(int(session_id))
        if not session.exists():
            return {'success': False, 'message': 'Session not found'}

        vals = {}
        for step in steps_data:
            step_id = step.get('id')
            content = step.get('content')
            if step_id and content:
                vals[f"step{step_id}_output_html"] = content

        if vals:
            session.write(vals)
            return {'success': True}
        return {'success': False, 'message': 'No data provided'}
