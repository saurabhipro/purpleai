# -*- coding: utf-8 -*-

from odoo import models, api, _
from odoo.exceptions import ValidationError


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.constrains('file_size', 'res_model', 'res_field')
    def _check_file_size_limit(self):
        """Override to allow larger files for tender_ai.job ZIP files"""
        for record in self:
            # Skip validation for tender_ai.job zip_file to allow larger files
            if record.res_model == 'tende_ai.job' and record.res_field == 'zip_file':
                # Allow up to 2GB for tender ZIP files
                max_size = 2 * 1024 * 1024 * 1024  # 2GB
                if record.file_size and record.file_size > max_size:
                    raise ValidationError(
                        _('File size (%.1f MB) exceeds maximum allowed size (2048 MB)') % 
                        (record.file_size / (1024*1024))
                    )
                # Skip default validation for this case
                continue
            else:
                # Use default validation for other attachments
                # Call parent method if it exists
                if hasattr(super(), '_check_file_size_limit'):
                    try:
                        super()._check_file_size_limit()
                    except AttributeError:
                        # Parent doesn't have this constraint, that's fine
                        pass

