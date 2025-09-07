# -- coding: utf-8 --
{
    # Module information
    'name': "Automatic Plaid Synchronization",
    "version": "18.0.1.0.0",
    "category": "Accounting",

    'description': """
        This module enables you to do Online bank synchronization via Plaid. It enables users to link bank journals to 
        their online bank accounts, for supported banking institutions via Plaid, and configure a periodic and automatic
         synchronization of their bank statements.  
    """,

    "license": "OPL-1",

    'summary': """
        This module is used for online bank account synchronization via Plaid. It enables user to link bank journals to 
        their online bank accounts for supported banking institutions via Plaid and configure a periodic and automatic 
        synchronization of their bank statements to get bank feeds directly in odoo. 
    """,

    # Author
    'author': "Axiom World",
    'website': "https://www.axiomworld.net",

    # Dependencies
    'depends': ['web', 'account'],

    'assets': {
        'web.assets_backend': [
            'plaid_sync/static/src/js/plaid_main.js',
            'plaid_sync/static/src/xml/plaid_action_view.xml',
        ],
    },
    # Views
    'data': [
        'security/ir.model.access.csv',
        'views/online_plaid_sync_views.xml',
        'views/res_config_settings.xml',
        'views/account_bank_statement.xml',
        'wizards/plaid_transactions_wizard_views.xml',
    ],

    "images":
        [
            'static/description/banner.gif',
            'static/description/icon.png',
        ],

    # Technical
    "installable": True,
    "auto_install": False,
    'price': 68,
    'currency': 'USD',
}
