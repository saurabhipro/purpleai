{
    'name': 'ARADA',
    'version': '1.0.0',
    'category': 'Real Estate',
   
    'author': 'Anjli',
    'website': 'https://www.bharatddn.com',
    'depends': [
        'mail'
    ],
    'data': [
        # 'views/larr_menu_views.xml',
        'security/ir.model.access.csv',
        'views/tenant_details.xml',
        # Remove: 'views/critical_path_views.xml',
        'views/workflow.xml',
        'views/menuitem.xml',

    ],
   
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
   
} 