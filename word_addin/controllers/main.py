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

        env = request.env(user=request.session.uid)
        session = env['memo_ai.session'].browse(int(session_id))
        if not session.exists():
            return {'error': 'session_not_found'}

        steps = []
        if step_num == 'all':
            steps = [
                {'id': 1, 'title': 'Step 1: Core Issues', 'content': session.step1_output},
                {'id': 2, 'title': 'Step 2: Legal Analysis', 'content': session.step2_output},
                {'id': 3, 'title': 'Step 3: Risk Assessment', 'content': session.step3_output},
                {'id': 4, 'title': 'Step 4: Final Recommendation', 'content': session.step4_output},
            ]
        else:
            step_attr = f"step{step_num}_output"
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

        env = request.env(user=request.session.uid)
        sessions = env['memo_ai.session'].search([
            ('create_uid', '=', request.session.uid)
        ], limit=5, order='write_date desc')
        
        return [{
            'id': s.id,
            'name': s.name,
            'subject': s.subject_id.name if s.subject_id else 'Generic',
            'date': s.write_date.strftime('%Y-%m-%d')
        } for s in sessions]

    @http.route('/word_addin/save_memo_data', type='json', auth='none', methods=['POST'], cors='*', csrf=False)
    def save_memo_data(self, session_id, html_content=None, steps_data=None):
        """Save data with CSRF disabled, parse document HTML if provided."""
        if not request.session.uid:
            return {'error': 'authentication_required'}

        env = request.env(user=request.session.uid)
        session = env['memo_ai.session'].browse(int(session_id))
        if not session.exists():
            return {'success': False, 'message': 'Session not found'}

        import re
        vals = {}
        
        # If the Add-in sent the full raw HTML
        if html_content:
            # Capture the entire HTML tag sequence leading up to "Step X"
            # This ensures we do NOT sever HTML tags (which would break the document display in Odoo)
            pattern = r'(?i)(<[^>]*?\b(?:h[1-6]|p|div|td)\b[^>]*>\s*(?:<[^>]+>\s*)*Step\s*([1-4])\b)'
            parts = re.split(pattern, html_content)
            
            if len(parts) > 1:
                # Since we have 2 capture groups in re.split, parts looks like:
                # [0: before, 1: delimiter_html, 2: step_digit, 3: content_after, 4: next_delimiter_html...]
                for i in range(1, len(parts), 3):
                    step_id = parts[i+1]
                    content_after = parts[i+2]
                    
                    # DO NOT save the delimiter back into Odoo (prevents duplicate headers on reload)
                    vals[f"step{step_id}_output"] = content_after.strip()
            else:
                # If no headers were found, just overwrite step 1 so they don't lose data
                vals['step1_output'] = html_content

        # Fallback for old Add-in versions
        elif steps_data:
            for step in steps_data:
                step_id = step.get('id')
                content = step.get('content')
                if step_id and content:
                    vals[f"step{step_id}_output"] = content

        if vals:
            session.write(vals)
            return {'success': True}
        return {'success': False, 'message': 'No data provided'}
