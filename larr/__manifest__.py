{
    'name': 'Land Acquisition and Rehabilitation',
    'version': '1.0.0',
    'category': 'Real Estate',
    'summary': 'Comprehensive Land Acquisition and Rehabilitation Management System',
    'description': """
        Land Acquisition and Rehabilitation (LARR) Module
        
        This module provides comprehensive management for:
        - Land acquisition processes
        - Rehabilitation and resettlement
        - Compensation management
        - Project tracking
        - Stakeholder management
        - Document management
        - Village master data
        - Survey management
        - Compliance tracking
    """,
    'author': 'Bharat DDN',
    'website': 'https://www.bharatddn.com',
    'depends': [
        'base',
        'mail',
        'hr',
        'project',
        'account',
        'web',
        'portal',
    ],
    'data': [
        # 'security/larr_security.xml',
        # 'security/ir.model.access.csv',
        # 'data/larr_sequence.xml',
        # 'data/larr_data.xml',
        # 'views/larr_project_views.xml',
        # 'views/larr_village_views.xml',
        # 'views/larr_district_views.xml',
        # 'views/larr_land_acquisition_views.xml',
        # 'views/larr_rehabilitation_views.xml',
        # 'views/larr_compensation_views.xml',
        # 'views/larr_stakeholder_views.xml',
        # 'views/larr_document_views.xml',
        # 'views/larr_dashboard_views.xml',
        # 'views/larr_owner_views.xml',
        # 'views/larr_survey_views.xml',
        # 'views/larr_menu_views.xml',
    ],
    'demo': [
        'demo/larr_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'assets': {
        'web.assets_backend': [
            # 'larr/static/src/js/larr_dashboard.js',
            # 'larr/static/src/css/larr_dashboard.css',
            # 'larr/static/src/css/larr_survey.css',
        ],
    },
} 