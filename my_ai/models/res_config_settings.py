# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    did_api_key = fields.Char(
        string='D-ID API Key',
        config_parameter='my_ai.did_api_key',
        help='Your D-ID API key. Get it from https://studio.d-id.com/'
    )
    
    did_api_url = fields.Char(
        string='D-ID API URL',
        default='https://api.d-id.com/talks',
        config_parameter='my_ai.did_api_url',
        help='D-ID API base URL'
    )
    
    did_default_avatar_url = fields.Char(
        string='Default Avatar Image URL',
        default='https://create-images-results.d-id.com/DefaultPresenters/Emma_f.jpg',
        config_parameter='my_ai.did_default_avatar_url',
        help='Default avatar image URL for video generation'
    )
    
    did_default_voice_id = fields.Char(
        string='Default Voice ID',
        default='en-US-JennyNeural',
        config_parameter='my_ai.did_default_voice_id',
        help='Default Microsoft voice ID (e.g., en-US-JennyNeural, en-US-GuyNeural)'
    )

