{
    'name': 'Tender AI - Automated Tender Processing',
    'version': '18.0.1.0.0',
    'summary': 'AI-powered tender processing for tender ZIP/PDF documents',
    'description': """
        Tender AI Module
        ================
        This module processes tender ZIP files using an AI extraction service to extract:
        - Tender information from tender.pdf
        - Bidder/company details from company folders
        - Payment records
        - Work experience records
        - Eligibility criteria
        
        Features:
        - Secure ZIP file upload and extraction
        - Background processing with job tracking
        - AI API integration for PDF extraction
        - Excel export of processed data
    """,
    'category': 'Tools',
    'author': 'Bhuarjan',
    'website': 'bhuarjan.com',
    'depends': ['base', 'mail', 'mail_bot', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/system_parameter_data.xml',
        'wizard/tender_ai_chat_wizard.xml',
        'views/tender_dashboard_owl_views.xml',
        'views/tender_dashboard_views.xml',
        'views/tender_job_views.xml',
        'views/tender_views.xml',
        'views/bidder_views.xml',
        'views/bidder_check_views.xml',
        'views/bidder_check_line_views.xml',
        'views/client_query_views.xml',
        'views/payment_views.xml',
        'views/work_experience_views.xml',
        'views/ir_attachment_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'tender_ai/static/src/css/tender_dashboard.css',
            'tender_ai/static/src/css/bidder_check_styles.css',
            'tender_ai/static/src/dashboard/css/tender_ai_dashboard.css',
            'tender_ai/static/src/dashboard/xml/tender_ai_dashboard.xml',
            'tender_ai/static/src/dashboard/js/tender_ai_dashboard.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
