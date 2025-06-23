# -*- coding: utf-8 -*-
{
    'name': 'Google Map Field',
    'version': '18.0.1.0.0',
    'summary': 'Google Map Location Picker with Autocomplete',
    'description': """This module will help to find any location from google map with autocomplete search and get latitude and longitude of selected location.""",
    'category': 'Extra Tools',
    'author': 'MAISOLUTIONSLLP',
    'maintainer': 'MAISOLUTIONSLLP',
    'company': 'MAISOLUTIONSLLP',
    'website': 'https://maismfg.com/',
    'depends': ['web'],
    'data': [
        # 'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'google_map_field/static/src/js/google_map_field.js',
            'google_map_field/static/src/scss/google_map_field.scss',
            'google_map_field/static/src/xml/google_map_field.xml',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
