# -*- coding: utf-8 -*-

import requests
import time
import logging
import base64
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DIDVideo(models.Model):
    _name = 'my.ai.did.video'
    _description = 'D-ID Video Generation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'title'
    _order = 'create_date desc'

    title = fields.Char(string='Title', required=True)
    upic_no = fields.Char(string='UPIC Number', help='Enter the UPIC number to generate personalized greeting video')
    property_id = fields.Many2one('ddn.property.info', string='Property', readonly=True)
    script_text = fields.Text(string='Script Text', required=True, help='Script will be auto-generated based on UPIC number')
    avatar_url = fields.Char(string='Avatar Image URL', help='Leave empty to use default avatar from settings')
    voice_id = fields.Char(string='Voice ID', help='Leave empty to use default voice from settings. For Hindi use: hi-IN-MadhurNeural or hi-IN-SwaraNeural')
    status = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('error', 'Error')
    ], string='Status', default='draft', readonly=True)
    
    @api.onchange('upic_no')
    def _onchange_upic_no(self):
        """Auto-generate script when UPIC number is entered"""
        if self.upic_no:
            property = self.env['ddn.property.info'].sudo().search([('upic_no', '=', self.upic_no.strip())], limit=1)
            if property:
                self.property_id = property.id
                # Generate personalized greeting script
                owner_name = property.owner_name or "Valued Customer"
                ddn_number = property.upic_no or "N/A"
                zone_name = property.zone_id.name if property.zone_id else "N/A"
                ward_name = property.ward_id.name if property.ward_id else "N/A"
                colony_name = property.colony_id.name if property.colony_id else "N/A"
                
                # Generate Hindi script
                self.script_text = f"""नमस्ते {owner_name},

भारत DDN में आपका स्वागत है!

आपका DDN नंबर {ddn_number} है।

आपकी संपत्ति जोन {zone_name}, वार्ड {ward_name}, और कॉलोनी {colony_name} में स्थित है।

भारत DDN का हिस्सा बनने के लिए धन्यवाद।"""
                
                # Set default Hindi voice if not set
                if not self.voice_id:
                    self.voice_id = 'hi-IN-MadhurNeural'  # Hindi male voice
                
                if not self.title:
                    self.title = f"Greeting Video - {ddn_number}"
            else:
                self.property_id = False
                self.script_text = ""
                return {
                    'warning': {
                        'title': 'Property Not Found',
                        'message': f'No property found with UPIC number: {self.upic_no}. Please check and try again.'
                    }
                }
    
    def _get_api_key(self):
        """Get API key from settings for Basic Authentication"""
        settings = self.env['my.ai.settings'].get_settings()
        api_key = settings.did_api_key or ''
        if api_key:
            # D-ID API uses Basic Auth with format: base64(username:password)
            # The API key might already be base64 encoded, or in format "username:password"
            # If it contains a colon, it's likely username:password format, encode it
            if ':' in api_key:
                # Encode username:password to base64 for Basic Auth
                import base64
                api_key = base64.b64encode(api_key.encode('utf-8')).decode('utf-8')
        return api_key.strip()
    
    def _get_api_url(self):
        """Get API URL from settings"""
        settings = self.env['my.ai.settings'].get_settings()
        return settings.did_api_url or 'https://api.d-id.com/talks'
    
    def _get_avatar_url(self):
        """Get avatar URL from record or settings"""
        if self.avatar_url:
            return self.avatar_url
        settings = self.env['my.ai.settings'].get_settings()
        return settings.did_default_avatar_url or 'https://d-id-public-bucket.s3.amazonaws.com/alice.jpg'
    
    def _get_voice_id(self):
        """Get voice ID from record or settings"""
        if self.voice_id:
            return self.voice_id
        settings = self.env['my.ai.settings'].get_settings()
        return settings.did_default_voice_id or 'hi-IN-MadhurNeural'
    
    # Video Results
    talk_id = fields.Char(string='Talk ID', readonly=True, help='D-ID Talk ID')
    video_url = fields.Char(string='Video URL', readonly=True)
    error_message = fields.Text(string='Error Message', readonly=True)
    
    # Document Storage
    attachment_id = fields.Many2one('ir.attachment', string='Video Attachment', readonly=True, ondelete='set null')
    shareable_link = fields.Char(string='Shareable Link', readonly=True, help='Public link to share the video')
    
    # Metadata
    create_date = fields.Datetime(string='Created On', readonly=True)
    write_date = fields.Datetime(string='Last Updated', readonly=True)

    def action_view_video(self):
        """Open video in new window"""
        self.ensure_one()
        if not self.video_url:
            raise UserError('No video URL available.')
        
        video_url = self.shareable_link if self.shareable_link else self.video_url
        return {
            'type': 'ir.actions.act_url',
            'url': video_url,
            'target': 'new',
        }

    def action_generate_video(self):
        """Generate video using D-ID API"""
        self.ensure_one()
        
        api_key = self._get_api_key()
        if not api_key:
            raise UserError('Please configure D-ID API Key in MyAI Settings first!')
        
        if not self.script_text:
            raise UserError('Please provide script text to generate the video')
        
        # Update status to processing
        self.write({'status': 'processing', 'error_message': False})
        
        try:
            # Create video
            talk_id = self._create_video()
            self.write({'talk_id': talk_id})
            
            # Check status and get video URL
            video_url = self._get_video_url(talk_id)
            self.write({
                'status': 'done',
                'video_url': video_url
            })
            
            # Automatically download and store video
            try:
                self.action_download_and_store_video()
            except Exception as e:
                _logger.warning(f"Could not auto-download video: {str(e)}")
                # Don't fail the whole process if download fails
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Video generated successfully!',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"Error generating video: {str(e)}")
            self.write({
                'status': 'error',
                'error_message': str(e)
            })
            raise UserError(f'Error generating video: {str(e)}')

    def _create_video(self):
        """Create video using D-ID API"""
        api_key = self._get_api_key()
        if not api_key:
            raise UserError('D-ID API Key is not configured. Please set it in MyAI Settings.')
        
        api_url = self._get_api_url()
        headers = {
            "Authorization": f"Basic {api_key}",
            "Content-Type": "application/json"
        }
        
        avatar_url = self._get_avatar_url()
        voice_id = self._get_voice_id()
        
        # Validate avatar URL is accessible (non-blocking - just log warnings)
        # D-ID API will validate the URL, so we just log warnings here
        if avatar_url:
            try:
                test_response = requests.head(avatar_url, timeout=5, allow_redirects=True)
                if test_response.status_code not in [200, 301, 302, 403]:
                    # 403 might be expected for some D-ID URLs, so we only warn
                    _logger.warning(f"Avatar URL might not be publicly accessible: {avatar_url} (Status: {test_response.status_code})")
            except Exception as e:
                # Don't block the request - let D-ID API handle validation
                _logger.warning(f"Could not validate avatar URL (non-blocking): {avatar_url}, Error: {str(e)}")
        
        # Build payload - D-ID talks endpoint requires source_url and script
        payload = {
            "source_url": avatar_url,
            "script": {
                "type": "text",
                "input": self.script_text.strip(),
                "provider": {
                    "type": "microsoft",
                    "voice_id": voice_id
                }
            }
        }
        
        # Remove empty or None values
        payload = {k: v for k, v in payload.items() if v is not None}
        if 'script' in payload and payload['script']:
            payload['script'] = {k: v for k, v in payload['script'].items() if v is not None}
            if 'provider' in payload['script'] and payload['script']['provider']:
                payload['script']['provider'] = {k: v for k, v in payload['script']['provider'].items() if v is not None}
        
        _logger.info(f"D-ID API Request - URL: {api_url}")
        _logger.info(f"D-ID API Payload: {payload}")
        _logger.info(f"D-ID API Headers (without key): {dict((k, '***' if k == 'Authorization' else v) for k, v in headers.items())}")
        
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            
            _logger.info(f"D-ID API Response Status: {response.status_code}")
            _logger.info(f"D-ID API Response: {response.text[:500]}")
            
            if response.status_code == 401:
                error_detail = response.text
                _logger.error(f"D-ID API 401 Unauthorized - Response: {error_detail}")
                raise UserError(f'D-ID API Authentication failed. Please check your API key in MyAI Settings. Error: {error_detail[:200]}')
            
            if response.status_code == 500:
                error_detail = response.text
                _logger.error(f"D-ID API 500 Internal Server Error - Response: {error_detail}")
                # Try to get more details from the response
                try:
                    error_json = response.json()
                    error_msg = error_json.get('description', error_json.get('message', error_detail))
                    raise UserError(f'D-ID API Internal Server Error. This might be due to invalid avatar URL or payload format. Error: {error_msg[:300]}')
                except:
                    raise UserError(f'D-ID API Internal Server Error. Please check the avatar URL and script text. Error: {error_detail[:300]}')
            
            response.raise_for_status()
            result = response.json()
            # D-ID API returns 'id' for talks endpoint
            talk_id = result.get("id") or result.get("talk_id")
            if not talk_id:
                _logger.error(f"D-ID API Response missing ID: {result}")
                raise UserError(f'D-ID API response missing talk ID. Response: {str(result)[:200]}')
            _logger.info(f"D-ID API Success - Talk ID: {talk_id}")
            return talk_id
        except requests.exceptions.HTTPError as e:
            error_detail = response.text if 'response' in locals() else str(e)
            status_code = e.response.status_code if hasattr(e, 'response') and hasattr(e.response, 'status_code') else 'Unknown'
            _logger.error(f"D-ID API HTTP Error - Status: {status_code}, Response: {error_detail}")
            raise UserError(f'D-ID API Error (Status {status_code}): {error_detail[:300]}')
        except Exception as e:
            _logger.error(f"D-ID API Unexpected Error: {str(e)}")
            raise UserError(f'Unexpected error: {str(e)}')

    def _get_video_url(self, talk_id, max_attempts=60):
        """Check video status and get URL when ready"""
        api_key = self._get_api_key()
        api_base_url = self._get_api_url()
        # Remove /talks if present to get base URL
        if api_base_url.endswith('/talks'):
            api_base_url = api_base_url[:-6]
        status_url = f"{api_base_url}/talks/{talk_id}"
        headers = {
            "Authorization": f"Basic {api_key}",
            "Content-Type": "application/json"
        }
        
        attempts = 0
        while attempts < max_attempts:
            response = requests.get(status_url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "done":
                return data.get("result_url")
            elif data.get("status") == "error":
                error_msg = data.get("error", {}).get("message", "Video generation failed")
                raise Exception(f"Video generation failed: {error_msg}")
            
            # Wait before next check
            time.sleep(5)
            attempts += 1
            
            # Update status message
            self._cr.commit()
        
        raise Exception("Video generation timed out. Please check the status manually.")

    def action_check_status(self):
        """Manually check video status"""
        self.ensure_one()
        
        if not self.talk_id:
            raise UserError('No Talk ID available. Please generate a video first.')
        
        api_key = self._get_api_key()
        if not api_key:
            raise UserError('Please configure D-ID API Key in MyAI Settings first!')
        
        try:
            video_url = self._get_video_url(self.talk_id)
            self.write({
                'status': 'done',
                'video_url': video_url
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Video is ready!',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error(f"Error checking status: {str(e)}")
            raise UserError(f'Error checking status: {str(e)}')

    def action_download_and_store_video(self):
        """Download video from URL and store as attachment"""
        self.ensure_one()
        
        if not self.video_url:
            raise UserError('No video URL available. Please generate a video first.')
        
        if self.attachment_id:
            raise UserError('Video is already stored as attachment.')
        
        try:
            # Download video
            response = requests.get(self.video_url, timeout=60, stream=True)
            response.raise_for_status()
            
            # Get video content
            video_content = response.content
            video_filename = f"{self.title or 'video'}_{self.id}.mp4"
            
            # Create attachment
            attachment = self.env['ir.attachment'].sudo().create({
                'name': video_filename,
                'type': 'binary',
                'datas': base64.b64encode(video_content).decode('utf-8'),
                'res_model': self._name,
                'res_id': self.id,
                'mimetype': 'video/mp4',
                'public': True,  # Make it publicly accessible
            })
            
            # Generate shareable link
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            shareable_link = f"{base_url}/web/content/{attachment.id}?download=false"
            
            self.write({
                'attachment_id': attachment.id,
                'shareable_link': shareable_link
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Video stored successfully! Shareable link: {shareable_link}',
                    'type': 'success',
                    'sticky': True,
                }
            }
            
        except Exception as e:
            _logger.error(f"Error downloading video: {str(e)}")
            raise UserError(f'Error downloading and storing video: {str(e)}')

