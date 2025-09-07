{
    'name': "Spotboxai Portal",
    'summary': "by this moduel user can self registerd by email phone and name company and ",
    'author': "Anjli Odoo Developer",

    'category': 'Account Portal',
    'version': '18.0',
    'depends': ['base', 'portal', 'product', 'all_in_one_sales_kit'],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_template.xml',
        'views/portal_order_line.xml',
        'views/sign_up.xml',
        'views/contact_template.xml',
        'views/order_template.xml',
        'views/menu_item.xml',
        'data/data.xml',
    ],
}

