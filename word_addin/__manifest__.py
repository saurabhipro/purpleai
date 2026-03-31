# -*- coding: utf-8 -*-
{
    'name': "Memo AI Word Add-in",
    'summary': "Open and edit AI Analysis Memo steps in Microsoft Word.",
    'description': """
        Integrates Odoo Memo AI sessions with Microsoft Word using Office.js.
        - Open specific steps in Word.
        - Open all steps at once.
        - Synchronize changes back to Odoo.
    """,
    'author': "Purple AI",
    'category': 'Productivity',
    'version': '18.0.1.0',
    'depends': ['memoai', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/taskpane_templates.xml',
        'views/launcher_wizard_views.xml',
        'views/memo_session_views_inherit.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
