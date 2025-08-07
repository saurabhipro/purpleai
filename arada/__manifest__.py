{
    'name': 'ARADA',
    'version': '1.0.0',
    'category': 'Real Estate',
   
    'author': 'Anjli',
    'website': 'https://www.bharatddn.com',
    'depends': [
        'base',
        'mail',
        'web',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/workflow_views.xml',
        'views/tenant_details.xml',
        'views/menuitem.xml',
    ],
   
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
   
} 