# -*- coding: utf-8 -*-

{
    'name': 'Odoo Email Attachment App',
    "author": "Edge Technologies",
    'version': '1.0',
    'live_test_url': "https://youtu.be/vr4defJtWLc",
    "images":['static/description/main_screenshot.png'], 
    'summary': 'Odoo email attachments send attachment with email send by email attachment option auto attach document on send by email option attach document on email document attachments',
    'description': 'Odoo email attachments send attachment with email send by email attachment option auto attach document on send by email option attach document on email document attachments',
    'license': "OPL-1",
    'depends': ['base','sale_management','account','purchase'],
    'data': [
        'views/inherited_sale_order_view.xml',
        'views/inherited_purchase_order_view.xml',
        'views/inherited_account_move_view.xml',
    ],
    # 'qweb': [
    #     "static/src/xml/attachment.xml",
    # ],
    'installable': True,
    'auto_install': False,
    'price': 8,
    'currency': "EUR",
    'category': 'Accounting',
}