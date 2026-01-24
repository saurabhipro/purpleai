{
    'name': 'Audit Tool (GT)',
    'version': '1.1',
    'summary': 'Audit Web Portal for Memo/Request Management',
    'description': """
        Audit Tool Module for GT.
        Allows Engagement Team to submit memos, obtain approval from Engagement Partner,
        and route through NPSG Team, Preparer, and Reviewers.
    """,
    'category': 'Services/Audit',
    'author': 'Antigravity',
    'depends': ['base', 'mail'],
    'data': [
        'security/audit_security.xml',
        'security/ir.model.access.csv',
        'views/audit_memo_views.xml',
        'views/audit_dashboard.xml',
        'views/menu.xml',
        'views/res_config_settings_views.xml',
        'data/audit_cron.xml',
        'demo/audit_demo.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
