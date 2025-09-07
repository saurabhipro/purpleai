# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
{
    "name": "Invoice Product Image, Serial Number, Tax Remove In Report",
    "author": "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "license": "OPL-1",
    "category": "Accounting",
    "summary": """
Invoice Product Management, Account Report App, Account Image Report Module,
Handle Invoice Serial Number, Tax Remove In Account Report, Account Report Management,
Bill Product Manage, Invoice Product Manage Odoo
""",
    "description": """
This module helps to manage the invoice Product. You can hide/show serial numbers,
product images & tax remove in the invoice & bill. If you want to show the product image
then you have an image size option in the product image.
Invoice Product Image, Serial Number, Tax Remove In Report Odoo
Manage Account Product In Report, Handle Goods In Account Report,
Manage Invoice Product In Report Module, Handle Image In Account Report,
Invoice Product Manage,  Management Of Serial Number In Report, Tax Remove In Bill Odoo.
Invoice Product Management, Account Report App, Account Image Report Module,
Handle Invoice Serial Number, Tax Remove In Account Report, Account Report Management,
Bill Product Manage, Invoice Product Manage Odoo
""",
    "version": "0.0.1",
    "depends": ["account"],
    "application": True,
    "data": [
            "views/account_move_views.xml",
            "reports/account_move_templates.xml",
            'views/sh_res_config_views.xml',
    ],
    "images": ["static/description/background.png", ],
    "auto_install": False,
    "installable": True,
    "price": 14,
    "currency": "EUR"
}
