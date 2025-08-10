# -*- coding: utf-8 -*-
{
    'name': "BPMN Modeler and Viewer",

    'summary': """
        BPMN Modeler and Viewer. Create BPMN Diagram in Odoo.
        """,

    'description': """
        BPMN Modeler and Viewer. Create BPMN Diagram in Odoo.
    """,

    'author': "RMT Works",
    'website': "https://github.com/rmtworks",
    'license': 'OPL-1',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'App/Customizations',
    'sequence': 1,
    "version": "18.2",

    # any module necessary for this one to work correctly
    'depends': ['base', 'web'],
    'data': [
        'security/groups.xml',
        'views/bpm.xml',
        'views/templates.xml',
        'security/ir.model.access.csv',
    ],
    'images': [
        'static/description/banner.png',
        'static/description/theme_screenshot.png',
        'static/description/icon.png',
    ],
    'assets': {
        'web.assets_backend': [
            'rmt_bpmn/static/src/js/libs/*/*.js',
            'rmt_bpmn/static/src/js/libs/*/*.css',
            'rmt_bpmn/static/src/js/*.js',
            'rmt_bpmn/static/src/xml/*.xml',
            'rmt_bpmn/static/src/scss/*.scss',
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
    'price': 28.00,
    'currency': 'EUR'
}
