# -*- coding: utf-8 -*-
{
    'name': 'Bizople DocEditor',
    'summary': 'Rich Word Document Editing in Odoo 18',
    'version': '1.0',
    'category': 'Productivity',
    'author': 'Bizople Solutions',
    'website': 'https://www.bizople.com',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/doc_document_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'https://cdn.ckeditor.com/ckeditor5/41.2.1/decoupled-document/ckeditor.js',
            'doceditor/static/src/scss/doceditor.scss',
            'doceditor/static/src/js/doceditor_client_action.js',
            'doceditor/static/src/xml/doceditor_client_action.xml',
        ],
    },
    'images': ['static/description/main_screenshot.png'],
    'installable': True,
    'application': True,
    'license': 'OPL-1',
}
