{
    'name': 'PurpleMaps',
    'version': '18.0.1.0.0',
    'summary': 'Interactive Entity Mapping & Structure Diagrams',
    'description': """
        PurpleMaps Module
        =============
        Interactive tools for creating ownership hierarchy diagrams and entity mapping.
    """,
    'category': 'Operations',
    'author': 'Bhuarjan',
    'website': 'bhuarjan.com',
    'depends': ['base', 'mail', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/demo_data.xml',
        'views/jigsaw_puzzle_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'jigsaw/static/src/workshop/**/*',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
