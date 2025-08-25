{
    'name': 'Arada',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Arada Management System',
    'description': """
        Arada Management System for tenant management and workflow processes.
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'mail', 'web', 'rmt_bpmn'],
    'data': [
        'security/arada_security.xml',
        'security/ir.model.access.csv',
        'views/config_views.xml',
        'views/ptl_views.xml',
        'views/workflow_views.xml',
        'wizard/approval_wizard.xml',
        'views/menuitem.xml',
    ],

    'assets': {
        'web.assets_backend': [
            # Components
            'arada/static/src/components/dashboard/dashboard.js',
            'arada/static/src/components/dashboard/dashboard.xml',
        ],

        

    },


    'demo': [],
    "images": ['arada/static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
} 