# -*- coding: utf-8 -*-
import io
import base64
import logging
import tempfile
import os
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PdfConverter(models.TransientModel):
    _name = 'purple_ai.pdf_converter'
    _description = 'Image to Searchable PDF Converter'

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'purple_ai_converter_att_rel',
        'converter_id', 'attachment_id',
        string='Images',
        help='Upload JPEG, PNG, TIFF or BMP images to convert and merge into one PDF'
    )
    lang = fields.Selection([
        ('eng',         'English only'),
        ('hin',         'Hindi only'),
        ('hin+eng',     'Hindi + English'),
        ('eng+hin+tam', 'English + Hindi + Tamil'),
        ('eng+hin+kan', 'English + Hindi + Kannada'),
        ('eng+ben',     'English + Bengali'),
        ('eng+mar',     'English + Marathi'),
    ], string='OCR Language', default='hin+eng', required=True)

    rotate_pages = fields.Boolean(
        string='Auto-Rotate Pages',
        default=True,
        help='Automatically correct orientation of skewed/rotated images'
    )

    output_pdf = fields.Binary(string='Download PDF', readonly=True, attachment=False)
    output_filename = fields.Char(default='searchable_merged.pdf')
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')
    page_count = fields.Integer(string='Pages processed', readonly=True)
    error_log = fields.Text(string='Errors', readonly=True)

    def action_convert(self):
        """OCR each uploaded image and merge into a single searchable PDF."""
        self.ensure_one()

        if not self.attachment_ids:
            raise UserError(_("Please upload at least one image before converting."))

        try:
            import pytesseract
            from PIL import Image as PILImage
        except ImportError:
            raise UserError(_(
                "pytesseract / Pillow not installed.\n"
                "Run: pip3 install pytesseract pillow --break-system-packages"
            ))

        try:
            import fitz
        except ImportError:
            raise UserError(_("PyMuPDF (fitz) not installed. Run: pip3 install pymupdf"))

        merged = fitz.open()
        errors = []
        page_count = 0

        for att in self.attachment_ids:
            if not att.datas:
                errors.append(f"{att.name}: no file data")
                continue

            tmp_img = None
            tmp_pdf_path = None
            try:
                # Write image to temp file
                img_bytes = base64.b64decode(att.datas)
                ext = os.path.splitext(att.name)[1].lower() or '.jpg'
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                    tmp_img = f.name
                    f.write(img_bytes)

                # Open with Pillow to validate and optionally auto-rotate
                pil_img = PILImage.open(tmp_img)
                if self.rotate_pages:
                    # EXIF-based auto-rotation
                    try:
                        from PIL import ImageOps
                        pil_img = ImageOps.exif_transpose(pil_img)
                    except Exception:
                        pass

                # Convert to RGB if needed (tesseract needs RGB or grayscale)
                if pil_img.mode not in ('RGB', 'L'):
                    pil_img = pil_img.convert('RGB')

                # OCR → searchable PDF bytes
                # Point to custom tessdata dir that has hin.traineddata installed
                TESSDATA_DIR = '/home/odoo18/tessdata'
                import os as _os
                _os.environ['TESSDATA_PREFIX'] = TESSDATA_DIR

                pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                    pil_img,
                    lang=self.lang,
                    extension='pdf',
                )

                # Open the OCR'd PDF and insert into merged doc
                page_pdf = fitz.open("pdf", pdf_bytes)
                merged.insert_pdf(page_pdf)
                page_pdf.close()
                page_count += 1

            except Exception as e:
                err = f"{att.name}: {str(e)}"
                _logger.error("PDF Converter error: %s", err)
                errors.append(err)
            finally:
                if tmp_img and os.path.exists(tmp_img):
                    os.remove(tmp_img)
                if tmp_pdf_path and os.path.exists(tmp_pdf_path):
                    os.remove(tmp_pdf_path)

        if page_count == 0:
            raise UserError(_(
                "No pages could be processed. Errors:\n%s"
            ) % "\n".join(errors))

        # Save merged PDF
        out = io.BytesIO()
        merged.save(out, garbage=4, deflate=True)
        merged.close()

        filename = f"searchable_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        self.write({
            'output_pdf': base64.b64encode(out.getvalue()),
            'output_filename': filename,
            'page_count': page_count,
            'state': 'done',
            'error_log': "\n".join(errors) if errors else False,
        })

        # Re-open the same wizard with the result
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self._context,
        }

    def action_reset(self):
        """Clear result and start fresh."""
        self.write({
            'output_pdf': False,
            'output_filename': 'searchable_merged.pdf',
            'state': 'draft',
            'page_count': 0,
            'error_log': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
