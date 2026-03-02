
import base64, os
from odoo import fields, models, api, tools
import logging
_logger = logging.getLogger(__name__)

class IrDefault(models.Model):
    _inherit = 'ir.default'

    @api.model
    def set_wk_favicon(self, model, field):
        script_dir = os.path.dirname(__file__)
        rel_path = "../static/src/img/favicon.png"
        abs_file_path = os.path.join(script_dir, rel_path)
        with open(abs_file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read())
            self.set('res.config.settings', 'wk_favicon', encoded_string.decode("utf-8"))

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    wk_favicon = fields.Binary(string="Favicon Image")
    title_brand = fields.Char(string="Title Brand")
    odoo_text_replacement = fields.Char(string='Replace Text "Odoo" With?')
    favicon_url = fields.Char(string="Url")
    attach_id = fields.Integer(string="Favicon Attach ID")

    @api.model
    def get_debranding_settings(self):
        IrDefault = self.env['ir.default'].sudo()
        wk_favicon = IrDefault._get('res.config.settings', "wk_favicon")
        title_brand = IrDefault._get('res.config.settings', "title_brand")
        odoo_text_replacement = IrDefault._get('res.config.settings', "odoo_text_replacement")
        favicon_url = IrDefault._get('res.config.settings', "favicon_url")
        attach_id = IrDefault._get('res.config.settings', "attach_id")
        result =  {
            'wk_favicon': wk_favicon,
            'attach_id' : attach_id,
            'title_brand': title_brand,
            'odoo_text_replacement': odoo_text_replacement,
            'favicon_url': favicon_url,
        }
      
        return result 

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        IrDefault = self.env['ir.default'].sudo()
        IrDefault.set('res.config.settings', "wk_favicon", self.wk_favicon.decode("utf-8"))
        IrDefault.set('res.config.settings', "title_brand", self.title_brand)
        IrDefault.set('res.config.settings', "odoo_text_replacement", self.odoo_text_replacement)
        if not self.attach_id:
            attach_id = self.env['ir.attachment'].sudo().search([('name', '=', 'Favicon')])
            if attach_id:
                attach_id.write({
                    'datas': self.wk_favicon.decode("utf-8"),
                })
            else:
                attach_id = self.env['ir.attachment'].sudo().create({
                    'name': 'Favicon',
                    'datas': self.wk_favicon.decode("utf-8"),
                    'public': True
                })
        else:
            attach_id.write({
                'datas': self.wk_favicon.decode("utf-8"),
            })
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        image_url = base_url+'/web/image/?model=ir.attachment&id='+str(attach_id.id)+'&field=datas'
        IrDefault.set('res.config.settings', "favicon_url", image_url)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        IrDefault = self.env['ir.default'].sudo()
        wk_favicon = IrDefault._get('res.config.settings', "wk_favicon")
        title_brand = IrDefault._get('res.config.settings', "title_brand")
        odoo_text_replacement = IrDefault._get('res.config.settings', "odoo_text_replacement")
        favicon_url = IrDefault._get('res.config.settings', 'favicon_url')
        attach_id = IrDefault._get('res.config.settings', 'attach_id')
        res.update(
            wk_favicon = wk_favicon,
            title_brand = title_brand,
            odoo_text_replacement = odoo_text_replacement,
            favicon_url = favicon_url,
            attach_id = attach_id,
        )
        return res
