# -*- coding: utf-8 -*-
{
    'name': "Ringover",

    'summary': """
        Make and receive calls and SMS, sync contacts, 
        capture conversation history and recordings right from your Odoo Platform (SaaS compatible)
    """,

    'description': """
        For Odoo 18 Cloud Platform (SaaS)
    """,

    'author': "Ringover",
    'website': "https://www.ringover.com/",

    'category': 'Productivity',
    'version': '1.0',
    'license': 'OPL-1',
    'application': True,
    'installable': True,
    'auto_install': False,


    # any module necessary for this one to work correctly
    'depends': ['base', 'web'],
    'data': [
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ringover_dialer/static/src/js/lib/ringover_constants.js',
            'ringover_dialer/static/src/js/lib/ringover_sdk.js',
            'ringover_dialer/static/src/services/ringover_service.js',
            'ringover_dialer/static/src/js/dialer.js',
            'ringover_dialer/static/src/scss/dialer.scss',
        ],
    },
    "images":["static/description/cover_thumbnail.png"],
    "cloc_exclude": ["static/**/*"],
}
