{
    'name': 'Memo AI - Intelligent Document Analysis',
    'version': '18.0.1.0.0',
    'summary': 'AI-powered step-by-step document analysis, issue identification, and regulatory guideline mapping',
    'description': """
        Memo AI Module
        ==============
        Features:
        - Subject-based AI analysis pipeline (5-step workflow)
        - RAG-powered Issue List, Guideline, and Analysis libraries
        - Step-by-step document summarization → issue extraction → regulatory mapping → analysis → Word export
        - SME-configurable prompts per subject
        - Editable AI outputs at every step
    """,
    'category': 'Operations/AI',
    'author': 'Bhuarjan',
    'website': 'bhuarjan.com',
    'depends': ['base', 'mail', 'web'],
    'data': [
        'security/memo_ai_security.xml',
        'security/ir.model.access.csv',
        'data/memo_subject_data.xml',
        'views/menu_root.xml',
        'views/res_config_settings_views.xml',
        'views/memo_subject_views.xml',
        'views/memo_rag_document_views.xml',
        'views/memo_session_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'memoai/static/src/components/memo_workflow/memo_workflow.js',
            'memoai/static/src/components/memo_workflow/memo_workflow.xml',
            'memoai/static/src/components/memo_workflow/memo_workflow.scss',
        ],
    },
    'installable': True,
    'application': True,
    'images': ['static/description/icon.png'],
    'license': 'LGPL-3',
}
