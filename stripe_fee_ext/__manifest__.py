# -*- coding: utf-8 -*-

{
    'name': 'Stripe Fees Extension',
    'version': '18.0.1.0',
    'author': 'Craftsync Technologies',
    'maintainer': 'Craftsync Technologies',
    'category': 'Accounting',
    'summary': """Collect Stripe processing fees from customer. Fees can be configured
 as fixed or percentage wise. Stripe processing fees will be 
 automatically visible on checkout.
 stripe, stripe charge, stripe_charge, stripe fee, fees,
 processing fees, paypal, acquirer, payment gateway, payment, payment fees, processing charge
 transaction charge, transaction fee, online payment fee, payment charge""",
    'description': """
Stripe Payment Acquirer Fees Extension: Collect Stripe processing fees from customer.
""",
    'website': 'https://www.craftsync.com',
    'license': 'OPL-1',
    'support':'info@craftsync.com',
    'depends': ['payment_stripe'],
    'data': [
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',
        'views/payment_form_template.xml',
    ],
    'demo': [],
    'application': True,
    'auto_install': False,
    'images': ['static/description/main_screen.gif'],
    'price': 59.99,
    'currency': 'USD'
}
