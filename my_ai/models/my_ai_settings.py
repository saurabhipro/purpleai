# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MyAISettings(models.Model):
    _name = 'my.ai.settings'
    _description = 'MyAI Settings'
    _rec_name = 'name'
    

    name = fields.Char(string='Name', default='MyAI Settings', required=True)
    active = fields.Boolean(string='Active', default=True)
    
    # D-ID Configuration
    did_api_key = fields.Char(
        string='D-ID API Key',
        required=True,
        help='Your D-ID API key. Get it from https://studio.d-id.com/'
    )
    
    did_api_url = fields.Char(
        string='D-ID API URL',
        default='https://api.d-id.com/talks',
        required=True,
        help='D-ID API base URL'
    )
    
    did_default_avatar_url = fields.Char(
        string='Default Avatar Image URL',
        default='https://create-images-results.d-id.com/DefaultPresenters/Emma_f.jpg',
        required=True,
        help='Default avatar image URL for video generation'
    )
    
    did_default_voice_id = fields.Char(
        string='Default Voice ID',
        default='en-US-JennyNeural',
        required=True,
        help='Default Microsoft voice ID (e.g., en-US-JennyNeural, en-US-GuyNeural)'
    )

    @api.model
    def get_settings(self):
        """Get the settings record, create if doesn't exist"""
        settings = self.search([('active', '=', True)], limit=1)
        if not settings:
            settings = self.search([], limit=1, order='id desc')
        if not settings:
            settings = self.create({
                'name': 'MyAI Settings',
                'active': True,
                'did_api_key': '',
                'did_api_url': 'https://api.d-id.com/talks',
                'did_default_avatar_url': 'https://create-images-results.d-id.com/DefaultPresenters/Emma_f.jpg',
                'did_default_voice_id': 'en-US-JennyNeural',
            })
        return settings
    

