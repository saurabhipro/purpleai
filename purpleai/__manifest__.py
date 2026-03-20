{
    'name': 'Purple AI - Folder-based AI Extraction',
    'version': '18.0.1.0.0',
    'summary': 'AI-powered folder monitoring and data extraction',
    'description': """
        Purple AI Module
        ================
        Features:
        - Monitor local folders for new PDFs
        - Automated AI extraction using Gemini
        - Client-wise extraction templates
        - SQL-powered property analytics
    """,
    'category': 'Operations/AI',
    'author': 'Bhuarjan',
    'website': 'bhuarjan.com',
    'depends': ['base', 'mail', 'web', 'account', 'purchase'],
    'data': [
        'security/purple_ai_security.xml',
        'security/ir.model.access.csv',
        'data/system_parameter_data.xml',
        'data/ir_cron_data.xml',
        'data/extraction_template_data.xml',
        'views/res_config_settings_views.xml',
        'views/menu_root.xml',
        'views/dashboard_views.xml',
        'views/extraction_master_views.xml',
        'wizard/upload_invoice_wizard_views.xml',
        'views/client_master_views.xml',
        'views/extraction_result_views.xml',
        'views/folder_explorer_views.xml',
        'views/invoice_processor_views.xml',
        'views/ir_attachment_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'purpleai/static/src/components/ai_evidence_viewer/ai_evidence_viewer.js',
            'purpleai/static/src/components/ai_evidence_viewer/ai_evidence_viewer.xml',
            'purpleai/static/src/components/ai_evidence_viewer/ai_evidence_viewer.scss',
            'purpleai/static/src/components/folder_explorer/folder_explorer.js',
            'purpleai/static/src/components/folder_explorer/folder_explorer.xml',
            'purpleai/static/src/components/folder_explorer/folder_explorer.scss',
            'purpleai/static/src/components/dashboard/dashboard.js',
            'purpleai/static/src/components/dashboard/dashboard.xml',
            'purpleai/static/src/components/dashboard/dashboard.scss',
            'purpleai/static/src/js/resizable_layout.js',
            'purpleai/static/src/js/scan_progress_listener.js',
        ],
    },
    'installable': True,
    'application': True,
    'images': ['static/description/logo.png'],
    'license': 'LGPL-3',
}
