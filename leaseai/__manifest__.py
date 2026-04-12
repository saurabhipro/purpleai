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
    'category': 'Operations/AI',
    'author': 'GT Bharat',
    'website': 'https://gtbharat.in',
    'images': ['static/description/icon.png'],
    'depends': ['base', 'mail', 'ai_core'],
    'data': [
        'security/ir.model.access.csv',
        'data/lease_template_data.xml',
        'views/menu_root.xml',
        'views/lease_template_views.xml',
        'views/lease_extraction_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
