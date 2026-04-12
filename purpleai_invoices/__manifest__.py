{
    'name': 'Purple Invoices - Folder-based AI Extraction',
    'version': '18.0.1.0.0',
    'summary': 'AI-powered folder monitoring and data extraction',
    'description': """
        Purple Invoices Module
        ================
        Features:
        - Monitor local folders for new PDFs
        - Automated AI extraction using Gemini
        - Client-wise extraction templates
        - SQL-powered property analytics
    """,
    'category': 'Operations/AI',
    'author': 'GT Bharat',
    'website': 'https://gtbharat.in',
    'depends': ['base', 'mail', 'web', 'ai_core'],
    'data': [
        'security/purple_ai_security.xml',
        'security/ir.model.access.csv',
        'data/system_parameter_data.xml',
        'data/ir_cron_data.xml',
        'data/extraction_template_data.xml',
        'data/student_exam_template.xml',
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
            'purpleai_invoices/static/src/components/ai_evidence_viewer/ai_evidence_viewer.js',
            'purpleai_invoices/static/src/components/ai_evidence_viewer/ai_evidence_viewer.xml',
            'purpleai_invoices/static/src/components/ai_evidence_viewer/ai_evidence_viewer.scss',
            'purpleai_invoices/static/src/components/folder_explorer/folder_explorer.js',
            'purpleai_invoices/static/src/components/folder_explorer/folder_explorer.xml',
            'purpleai_invoices/static/src/components/folder_explorer/folder_explorer.scss',
            'purpleai_invoices/static/src/components/dashboard/dashboard.js',
            'purpleai_invoices/static/src/components/dashboard/dashboard.xml',
            'purpleai_invoices/static/src/components/dashboard/dashboard.scss',
            'purpleai_invoices/static/src/js/resizable_layout.js',
            'purpleai_invoices/static/src/js/scan_progress_listener.js',
        ],
    },
    'installable': True,
    'application': True,
    'images': ['static/description/logo.png'],
    'license': 'LGPL-3',
}
