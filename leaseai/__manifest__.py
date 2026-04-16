{
    'name': 'Lease AI - Custom Prompt Extraction',
    'version': '18.0.1.0.0',
    'summary': 'Lease extraction with custom AI prompts',
    'description': """
        Lease AI
        ========
        Upload lease documents and extract structured information
        using custom prompts powered by centralized AI Core settings.
    """,
    'category': 'Purple AI',
    'author': 'GT Bharat',
    'website': 'https://gtbharat.in',
    'images': ['static/description/icon.png'],
    'depends': ['base', 'mail', 'web', 'ai_core', 'invoiceai'],
    'data': [
        'security/ir.model.access.csv',
        'data/lease_template_data.xml',
        'views/menu_root.xml',
        'views/lease_template_views.xml',
        'views/lease_extraction_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'leaseai/static/src/css/lease_extraction_layout.scss',
            'invoiceai/static/src/js/resizable_layout.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
