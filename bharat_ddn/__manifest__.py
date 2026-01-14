# -*- coding: utf-8 -*-
{
    'name': 'Bharat DDN',
    'summary': """
        Digital Pata
    """,
    'description': """
        Property Survey Management 
    """,
    'author': 'IPROSONIC',
    'website': 'https://www.iprosonic.com',
    'category': 'Services/Property',
    'version': '0.1',
    'depends': ['base', 'mail', 'web', 'website'],
    'data': [
        # Security
        'security/ir_rule.xml',
        'security/ir.model.access.csv',
        
        
        # Views
        'views/zone_views.xml',
        'views/ward_views.xml',
        'views/colony_views.xml',
        'views/property_type_views.xml',
        'views/property_views.xml',
        'views/property_map_view.xml',
        'views/res_users_views.xml',
        'views/mobile_otp_views.xml',
        'views/jwt_token_views.xml',
        'views/property_survey_views.xml',
        'views/property_group_views.xml',
        'views/services_views.xml',
        'wizard/create_property.xml',
        'views/res_company_views.xml',
        'wizard/property_import_wizard_view.xml',
        'wizard/ddn_report.xml',
        'wizard/delete_surveys_wizard.xml',
        'wizard/qr_scan_export_wizard.xml',
        'views/dashboard.xml',
        'views/indore_microsite.xml',
        'views/sambhaji_microsite.xml',
        'views/property_id_data_views.xml',
        'views/qr_scan_views.xml',
        'views/menuitems.xml',  # Load menus last

        # 'views/assets.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Components
            'bharat_ddn/static/src/components/graph/graph.js',
            'bharat_ddn/static/src/components/graph/graph.xml',
            'bharat_ddn/static/src/components/google_map/property_map.js',
            'bharat_ddn/static/src/components/google_map/property_map_template.xml',
            'bharat_ddn/static/src/components/dashboard/dashboard.js',
            'bharat_ddn/static/src/components/dashboard/dashboard.xml',
            'bharat_ddn/static/src/components/dashboard/dashboard.scss',
            'bharat_ddn/static/xml/hide_notification.xml',
            'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css',
            'https://maps.googleapis.com/maps/api/js?key=AIzaSyCQ1XvoKRmX1qqo2XwlLj2C2gCIiCjtgFE',
            'bharat_ddn/static/src/js/kml_viewer.js',
            'bharat_ddn/static/src/xml/kml_viewer.xml',
            'https://unpkg.com/leaflet/dist/leaflet.js',
            'https://unpkg.com/leaflet-omnivore/leaflet-omnivore.min.js',
            'https://unpkg.com/leaflet/dist/leaflet.css',
            'https://maps.googleapis.com/maps/api/js?key=AIzaSyCQ1XvoKRmX1qqo2XwlLj2C2gCIiCjtgFE',
            # https://maps.googleapis.com/maps/api/js?key=AIzaSyCQ1XvoKRmX1qqo2XwlLj2C,
            'bharat_ddn/static/src/libs/chart.js',
        ],

        'web.assets_frontend': [
            'bharat_ddn/static/src/scss/microsite.scss',
        ],

    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
