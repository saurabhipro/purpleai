# -*- coding: utf-8 -*
# Part of 4Minds. See LICENSE file for full copyright and licensing details.
{
    "name": "Many2many attachment preview",
    'version': '17.0',
    'author': 'TechEmpyre',
    'category': 'Tools',
    'summary': """ The Many2many Attachment Preview module enhances the functionality of attachments within Odoo by providing a streamlined preview feature for attachments linked to many2many fields. This module is particularly useful in scenarios where users need quick access to view multiple attachments associated with a record, such as documents, images, or other file types.""",
    'description': """ The Many2many Attachment Preview module enhances the functionality of attachments within Odoo by providing a streamlined preview feature for attachments linked to many2many fields. This module is particularly useful in scenarios where users need quick access to view multiple attachments associated with a record, such as documents, images, or other file types.""",
    "depends": ['base'],
    'assets': {
        'web.assets_backend': [
            'many2many_attachments_preview/static/src/xml/many2many_field_binary_preview_template.xml',
            'many2many_attachments_preview/static/src/js/many2many_field_binary_preview.js',
        ],
    },
    'images': ['static/description/main_screen.png'],
    'currency': 'USD',
    'price': 10,
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'OPL-1',
}
