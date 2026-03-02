# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
# Developed by Bizople Solutions Pvt. Ltd.
from odoo import http, SUPERUSER_ID
from odoo.http import request
from odoo.exceptions import AccessError

import logging
_logger = logging.getLogger(__name__)


class BackendConfigrationRec(http.Controller):

    @http.route(['/get/records/global/search'], type='json', auth='user')
    def get_global_searchdata(self, **kw):
        _logger.info('*****************************************8')
        user = request.env.user

        # Define the domain to filter records based on user rights
        domain = self._get_user_specific_domain(user)

        # Fetch the records with the domain applied
        globalsearchobj = request.env['global.search.bizople'].sudo()
        global_search_ids = globalsearchobj.search(domain)

        global_search_ids_list = []
        for record in global_search_ids:
            record_dict = {
                'id': record.id,
                'name': record.name,
                'models': record.global_model_id.name,
                'model_name': record.global_model_id.model,
            }
            global_search_ids_list.append(record_dict)

        return global_search_ids_list

    def _get_user_specific_domain(self, user):
        # Get the installed modules
        installed_modules = request.env['ir.module.module'].sudo(False).search([('state', '=', 'installed')])

        # Prepare a list to store modules with user rights information
        modules_with_user_rights = []

        # Loop through each installed module
        for module in installed_modules:
            # Get the groups related to the module
            groups = request.env['ir.model.data'].sudo().search([
                ('module', '=', module.name),
                ('model', '=', 'res.groups')
            ]).mapped('res_id')

            # Check if the user has rights for any of the groups related to the module
            user_has_rights = any(group_id in user.groups_id.ids for group_id in groups)

            # Append the module information with user rights status
            if user_has_rights:
                modules_with_user_rights.append({
                    'module_name': module.name,
                    'module_state': module.state,
                    'user_has_rights': user_has_rights
                })

        # Extract only the module names
        module_names = [module['module_name'] for module in modules_with_user_rights]

        installed_models = request.env['ir.model'].sudo().search([('modules', 'in', module_names)]).mapped('model')

        # Get all models the user has access to
        accessible_models = []
        for model in installed_models:
            if user.has_group('base.group_user'):
                try:
                    if request.env[model].sudo().has_access('read'):
                        accessible_models.append(model)
                except KeyError:
                    # Skip models that don't exist in the registry
                    continue

        # Create domain to filter records based on accessible models
        domain = [('global_model_id.model', 'in', accessible_models)]
        return domain

    @http.route(['/get/records/data'], type='json', auth='public')
    def get_records_icondata(self, **kw):
        domain = []
        app_rec_dict = []
        user = request.env.user

        # Get the model and id from the request
        model_name = kw.get('model')
        search_vals = kw.get('searchvals')
        global_search = request.env['global.search.bizople'].sudo().browse(int(kw.get('id')))

        if global_search:
            field_match_counts = {}
            field_strings = {}
            field_values = {}
            total_fields = len(global_search.global_field_ids)
            _logger.info('Total fields: %s', total_fields)

            if global_search.global_field_ids:
                total_fields = len(global_search.global_field_ids)

                for field in global_search.global_field_ids:
                    if field.name == 'display_name' or field.name == 'name':
                        # continue
                        domain.append(('name', 'ilike', kw.get('searchvals')))
                        try:
                            # _logger.info(' Try ===> %s ', model_name)
                            if user.id != SUPERUSER_ID:
                                records = request.env[model_name].sudo(False).search(domain)
                            else:
                                records = request.env[model_name].sudo().search(domain)
                        except AccessError:
                            _logger.info(' AccessError ===> %s ', model_name)
                            continue # Skip fields the user can't access
                        field_string = request.env[str(kw.get('model'))]._fields[field.name].string
                        match_count = len(records) if records else 0
                        field_match_counts[field.name] = match_count
                        field_strings[field.name] = field_string
                    else:
                        if field.relation:
                            field_model = str(field.relation)
                            if not request.env[field_model].has_access('read'):
                                continue # Skip fields the user can't access field relation
                            else:
                                domain.append((field.name, 'ilike', kw.get('searchvals')))

                                field_string = request.env[str(kw.get('model'))]._fields[field.name].string
                                domain_count = [(field.name, 'ilike', kw.get('searchvals'))]

                                # Check user access rights for the model
                                if not request.env[model_name].has_access('read'):
                                    return {'error': 'You do not have access rights to view this model.'}

                                try:
                                    # _logger.info(' Try ===> %s ', model_name)
                                    if user.id != SUPERUSER_ID:
                                        records = request.env[model_name].sudo(False).search(domain_count)
                                    else:
                                        records = request.env[model_name].sudo().search(domain_count)
                                except AccessError:
                                    _logger.info(' AccessError ===> %s ', model_name)
                                    continue # Skip fields the user can't access

                                match_count = len(records)
                                field_match_counts[field.name] = match_count
                                field_strings[field.name] = field_string
                        else:
                            domain.append((field.name, 'ilike', kw.get('searchvals')))

                            field_string = request.env[str(kw.get('model'))]._fields[field.name].string
                            domain_count = [(field.name, 'ilike', kw.get('searchvals'))]

                            # Check user access rights for the model
                            if not request.env[model_name].has_access('read'):
                                return {'error': 'You do not have access rights to view this model.'}

                            try:
                                # _logger.info(' Try ===> %s ', model_name)
                                if user.id != SUPERUSER_ID:
                                    records = request.env[model_name].sudo(False).search(domain_count)
                                else:
                                    records = request.env[model_name].sudo().search(domain_count)
                            except AccessError:
                                _logger.info(' AccessError ===> %s ', model_name)
                                continue # Skip fields the user can't access

                            match_count = len(records)
                            field_match_counts[field.name] = match_count
                            field_strings[field.name] = field_string

        domain_1 = []
        for no in range(len(domain) - 1):
            domain_1.append('|',)
        domain_1.extend(domain)

        if not field_match_counts:
            return []

        # Find the field with the highest match count
        most_relevant_field = max(field_match_counts, key=field_match_counts.get)
        most_relevant_field_string = field_strings[most_relevant_field]

        if domain_1:
            try:
                if user.id != SUPERUSER_ID:
                    records = request.env[model_name].sudo(False).search(domain_1)
                else:
                    records = request.env[model_name].sudo().search(domain_1)
            except AccessError:
                return []

            for rec in records:
                rec_field_values = {}
                for field in global_search.global_field_ids:
                    if field.ttype == 'many2one':
                        # rec_field_values[field.name] = rec[field.name].display_name
                        try:
                            rec_field_values[field.name] = rec[field.name].display_name
                        except Exception as e:
                            # Handle the error or log it as needed
                            rec_field_values[field.name] = 'Error: ' + str(e)
                    elif field.ttype == 'many2many':
                        # rec_field_values[field.name] = ', '.join(rec[field.name].mapped('display_name'))
                        try:
                            rec_field_values[field.name] = ', '.join(str(value) for value in rec[field.name].mapped('display_name'))
                        except Exception as e:
                            # Handle the error or log it as needed
                            rec_field_values[field.name] = 'Error: ' + str(e)
                    elif field.ttype == 'one2many':
                        # rec_field_values[field.name] = ', '.join(rec[field.name].mapped('display_name'))
                        try:
                            rec_field_values[field.name] = ', '.join(str(value) for value in rec[field.name].mapped('display_name'))
                        except Exception as e:
                            # Handle the error or log it as needed
                            rec_field_values[field.name] = 'Error: ' + str(e)
                    else:
                        rec_field_values[field.name] = rec[field.name]

                most_relevant_field_value = rec_field_values[most_relevant_field]

                if most_relevant_field_value:
                    vals = {
                        'rec_id': rec.id,
                        'rec_name': rec.display_name,
                        'display_name': f"{rec.display_name} | {most_relevant_field_string} : {most_relevant_field_value}",
                    }
                else:
                    vals = {
                        'rec_id': rec.id,
                        'rec_name': rec.display_name,
                        'display_name': f"{rec.display_name}",
                    }
                app_rec_dict.append(vals)
        return app_rec_dict
