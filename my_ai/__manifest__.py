# -*- coding: utf-8 -*-
{
    'name': 'MyAI',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'MyAI Module for Bharat DDN',
    'description': """
MyAI Module
===========
A custom AI module for Bharat DDN project.
    """,
    'author': 'Bharat DDN',
    'website': 'https://www.bharatddn.com',
    'depends': ['base', 'web', 'mail', 'bharat_ddn'],
    'data': [
        'security/ir.model.access.csv',
        'data/my_ai_settings_data.xml',
        'views/my_ai_views.xml',
        'views/my_ai_settings_views.xml',
        'views/did_video_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Add your JS/CSS assets here if needed
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

