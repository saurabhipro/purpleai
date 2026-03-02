# -*- coding: utf-8 -*-

from . import models

def pre_init_check(cr):
    from odoo.service import common
    from odoo.exceptions import ValidationError
    version_info = common.exp_version()
    server_serie = version_info.get('server_serie')
    if server_serie != '18.0':
        raise ValidationError(
            'Module support Odoo series 18.0 found {}.'.format(server_serie))
    return True