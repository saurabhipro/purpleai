
{
  "name"                 :  "Odoo Backend Debranding",
  "summary"              :  """This is the base odoo backend debranding module.""",
  "category"             :  "Extra Tools",
  "version"              :  "18.0",
  "sequence"             :  1,
  "author"               :  "Anjli Odoo Developer",
  "license"              :  "Other proprietary",
  "depends"              :  [
                             'web',
                             'mail',
                             'portal',
                            ],
  "data"                 :  [
                             'views/res_config_view.xml',
                             'views/web_client_template.xml',
                             'views/portal_templates.xml',
                             'views/email_templates.xml',
                             'views/res_users.xml',
                             'data/data.xml',
                            ],
  "qweb"                 :  [
                             'static/src/xml/base.xml',
                             'static/src/xml/client_action.xml',
                            ],
  "assets"               : {  
                            "web.assets_backend": [
                                # '/debrand_odoo/static/src/js/web_client.js',
                                '/debrand_odoo/static/src/js/dialog.js',
                                '/debrand_odoo/static/src/js/my_widget.js',
                                '/debrand_odoo/static/src/js/user_menu.js',
                                '/debrand_odoo/static/src/js/mail_dialog.js'
                            ],
                            'web.assets_qweb': [
                                'debrand_odoo/static/src/xml/dashboard.xml',
                                'debrand_odoo/static/src/xml/base.xml',
                                'debrand_odoo/static/src/xml/client_action.xml',
                            ],
                         },
  "images"               :  [''],
  "application"          :  True,
  "installable"          :  True,
  "auto_install"         :  False,
}
