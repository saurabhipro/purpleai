{
    'name': 'Invoice AI - Folder-based AI Extraction',
    'version': '18.0.1.0.7',
    'summary': 'AI-powered folder monitoring and data extraction',
    'description': """
        Install this app from Apps (or ``-i invoiceai``) on each database; models such as
        ``purple_ai.extraction_result`` exist only after installation. Put the ``invoiceai``
        folder on your Odoo ``addons_path`` (avoid duplicate legacy folders on the same path).

        Invoice AI Module
        ================
        Features:
        - Monitor local folders for new PDFs
        - Automated AI extraction using Gemini
        - Client-wise extraction templates
        - SQL-powered property analytics
    """,
    'category': 'Purple AI',
    'author': 'GT Bharat',
    'website': 'https://gtbharat.in',
    'depends': ['base', 'mail', 'web', 'ai_core'],
    'data': [
        'security/purple_ai_security.xml',
        'security/ir.model.access.csv',
        'data/system_parameter_data.xml',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/extraction_template_data.xml',
        'data/invoice_processor_dummy_data.xml',
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
        'views/pdf_converter_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'invoiceai/static/src/components/ai_evidence_viewer/ai_evidence_viewer.js',
            'invoiceai/static/src/components/ai_evidence_viewer/ai_evidence_viewer.xml',
            'invoiceai/static/src/components/ai_evidence_viewer/ai_evidence_viewer.scss',
            'invoiceai/static/src/components/folder_explorer/folder_explorer.js',
            'invoiceai/static/src/components/folder_explorer/folder_explorer.xml',
            'invoiceai/static/src/components/folder_explorer/folder_explorer.scss',
            'invoiceai/static/src/components/dashboard/dashboard.js',
            'invoiceai/static/src/components/dashboard/dashboard.xml',
            'invoiceai/static/src/components/dashboard/dashboard.scss',
            'invoiceai/static/src/js/resizable_layout.js',
            'invoiceai/static/src/js/scan_progress_listener.js',
        ],
    },
    'installable': True,
    'application': True,
    'images': ['static/description/logo.png'],
    'license': 'LGPL-3',
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
}
