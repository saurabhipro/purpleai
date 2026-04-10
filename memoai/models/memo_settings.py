# -*- coding: utf-8 -*-
# Memo AI settings have been deprecated. All AI configuration now lives in ai_core.settings.
# This file is kept for backward compatibility but contains no fields.

from odoo import models

class MemoAIResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    # No fields defined here; use ai_core.settings instead.
