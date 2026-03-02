# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
# Developed by Bizople Solutions Pvt. Ltd.
import datetime
from odoo import http, fields,_,SUPERUSER_ID
from odoo.http import request
from odoo.addons.web.controllers.dataset import DataSet as primary_colorDataset
from ast import literal_eval
from odoo.addons.web.controllers.webmanifest import WebManifest as SpiffyWebManifest
from odoo.exceptions import AccessError,AccessDenied
from odoo.models import check_method_name
import json
import operator
import re
import mimetypes
import base64
from odoo.addons.web.controllers.export import GroupsTreeNode,ExportXlsxWriter,GroupExportXlsxWriter
from odoo.tools import pycompat,file_open
from odoo.addons.mail.models.discuss.mail_guest import add_guest_to_context
from werkzeug.exceptions import NotFound
from odoo.addons.auth_totp.controllers.home import Home
from odoo.addons.web.controllers.session import Session
from collections import deque
import io
from odoo.tools import ustr, osutil
from odoo.tools.misc import xlsxwriter

import werkzeug.exceptions
from werkzeug.urls import url_parse
from odoo.http import content_disposition, request
from odoo.tools.safe_eval import safe_eval, time
from odoo.addons.web.controllers.export import ExcelExport
from odoo.exceptions import UserError

TRUSTED_DEVICE_COOKIE = 'td_id'
TRUSTED_DEVICE_AGE = 90*86400 # 90 days expiration

class BackendConfigration(http.Controller):

    @http.route(['/color/pallet/'], type='json', auth='public')
    def get_selected_pallet(self, **kw):
        config_vals = {}
        current_user = request.env.user
        app_light_bg_image = kw.get('app_light_bg_image')

        if app_light_bg_image:
            if 'data:image/' in str(app_light_bg_image):
                light_bg_file = str(app_light_bg_image).split(',')
                app_light_bg_file_mimetype = light_bg_file[0]
                app_light_bg_image = light_bg_file[1]
            else:
                light_bg_file = str(app_light_bg_image).split("'")
                app_light_bg_image = light_bg_file[1]
        else:
            app_light_bg_image = False

        app_menu_bg_image = kw.get('app_menu_bg_image')

        if app_menu_bg_image:
            if 'data:image/' in str(app_menu_bg_image):
                menu_bg_file = str(app_menu_bg_image).split(',')
                app_menu_bg_file_mimetype = menu_bg_file[0]
                app_menu_bg_image = menu_bg_file[1]
            else:
                menu_bg_file = str(app_menu_bg_image).split("'")
                app_menu_bg_image = menu_bg_file[1]
        else:
            app_menu_bg_image = False

        config_vals.update({
            'light_primary_bg_color': kw.get('light_primary_bg_color'),
            'light_primary_text_color': kw.get('light_primary_text_color'),
            'light_bg_image': app_light_bg_image,
            'apply_light_bg_img': kw.get('apply_light_bg_img'),
            'menu_bg_image': app_menu_bg_image,
            'tree_form_split_view': kw.get('tree_form_split_view'),
            'attachment_in_tree_view': kw.get('attachment_in_tree_view'),
            'separator': kw.get('selected_separator'),
            'tab': kw.get('selected_tab'),
            'checkbox': kw.get('selected_checkbox'),
            'radio': kw.get('selected_radio'),
            'popup': kw.get('selected_popup'),
            'use_custom_colors': kw.get('custom_color_pallet'),
            'color_pallet': kw.get('selected_color_pallet'),
            'appdrawer_custom_bg_color': kw.get('custom_drawer_bg'),
            'appdrawer_custom_text_color': kw.get('custom_drawer_text'),
            'header_vertical_mini_text_color': kw.get('custom_header_text'),
            'header_vertical_mini_bg_color': kw.get('custom_header_bg'),
            'menu_shape_bg_color': kw.get('menu_shape_bg'),
            'menu_shape_bg_color_opacity': kw.get('menu_shape_bg_color_opacity'),
            'use_custom_drawer_color': kw.get('custom_drawer_color_pallet'),
            'drawer_color_pallet': kw.get('selected_drawer_color_pallet'),
            'loader_style': kw.get('selected_loader'),
            'font_family': kw.get('selected_fonts'),
            'font_size': kw.get('selected_fontsize'),
            'top_menu_position': kw.get('selected_top_menu_position'),
            'top_menu_bg_vertical_mini_2': kw.get('selected_top_menu_bg_vertical_mini_2'),
            'vertical_mini_bg_image_one': kw.get('vertical_mini_bg_image_one'),
            'vertical_mini_bg_image_two': kw.get('vertical_mini_bg_image_two'),
            'vertical_mini_bg_image_three': kw.get('vertical_mini_bg_image_three'),
            'vertical_mini_bg_image_four': kw.get('vertical_mini_bg_image_four'),
            'theme_style': kw.get('selected_theme_style'),
            'apply_menu_shape_style': kw.get('apply_menu_shape_style'),
            'shape_style': kw.get('selected_menu_shape'),
            'list_view_density': kw.get('selected_list_view_density'),
            'list_view_sticky_header': kw.get('selected_list_view_sticky_header'),
            'input_style': kw.get('selected_input_style'),
        })

        if current_user.backend_theme_config:
            current_user.backend_theme_config.sudo().update(config_vals)
        else:
            backend_config_record = request.env['backend.config'].sudo().create(
                config_vals)
            current_user.sudo().write({
                'backend_theme_config': backend_config_record.id
            })

        return True

    @http.route(['/color/pallet/data/'], type='http', auth='public', sitemap=False)
    def selected_pallet_data(self, **kw):
        company = request.env.company
        user = request.env.user
        admin_users = request.env['res.users'].sudo().search([
            ('groups_id', 'in', request.env.ref('base.user_admin').id),
            ('backend_theme_config', '!=', False),
        ], order="id asc", limit=1)

        admin_config = False
        if admin_users:
            admin_config = admin_users.backend_theme_config

        if company.backend_theme_level == 'user_level':
            if user.backend_theme_config:
                config_vals = user.backend_theme_config
            elif admin_config:
                config_vals = admin_config
            else:
                config_vals = request.env['backend.config'].sudo().search(
                    [], order="id asc", limit=1)
        else:
            if admin_config:
                config_vals = admin_config
            else:
                config_vals = request.env['backend.config'].sudo().search(
                    [], order="id asc", limit=1)

        values = {}
        separator_selection_dict = dict(
            config_vals._fields['separator'].selection)
        tab_selection_dict = dict(config_vals._fields['tab'].selection)
        checkbox_selection_dict = dict(
            config_vals._fields['checkbox'].selection)
        radio_selection_dict = dict(config_vals._fields['radio'].selection)
        popup_selection_dict = dict(config_vals._fields['popup'].selection)
        light_bg_image = config_vals.light_bg_image
        values.update({
            'config_vals': config_vals,
            'separator_selection_dict': separator_selection_dict,
            'tab_selection_dict': tab_selection_dict,
            'checkbox_selection_dict': checkbox_selection_dict,
            'radio_selection_dict': radio_selection_dict,
            'popup_selection_dict': popup_selection_dict,
            'app_background_image': light_bg_image,
        })

        response = request.render(
            "spiffy_theme_backend.template_backend_config_data", values)

        return response

    @http.route(['/get/model/record'], type='json', auth='public')
    def get_record_data(self, **kw):
        company = request.env.company
        user = request.env.user
        admin_group_id = request.env.ref('base.user_admin').id
        is_admin = False
        if admin_group_id in user.groups_id.ids:
            is_admin = True
        admin_users = request.env['res.users'].sudo().search([
            ('groups_id', 'in', request.env.ref('base.user_admin').id),
            ('backend_theme_config', '!=', False),
        ], order="id asc", limit=1)
        admin_users_ids = admin_users.ids
        admin_config = False
        if admin_users:
            admin_config = admin_users.backend_theme_config
        show_edit_mode = True
        for admin in admin_users:
            if admin.backend_theme_config:
                admin_config = admin.backend_theme_config
                break
            else:
                continue

        if company.backend_theme_level == 'user_level':
            if user.backend_theme_config:
                record_vals = user.backend_theme_config
            elif admin_config:
                record_vals = admin_config
            else:
                record_vals = request.env['backend.config'].sudo().search(
                    [], order="id asc", limit=1)
        else:
            if not user.id in admin_users_ids:
                show_edit_mode = False
            if admin_config:
                record_vals = admin_config
            else:
                record_vals = request.env['backend.config'].sudo().search(
                    [], order="id asc", limit=1)

        prod_obj = request.env['backend.config']
        record_dict = record_vals.read(set(prod_obj._fields))
        if user.dark_mode:
            darkmode = "dark_mode"
        else:
            darkmode = False
        if user.vertical_sidebar_pinned:
            pinned_sidebar = "pinned"
        else:
            pinned_sidebar = False

        
        if company.prevent_auto_save:
            prevent_auto_save = "prevent_auto_save"
        else:
            prevent_auto_save = False

        if user.enable_todo_list:
            todo_list_enable = "enable_todo_list"
        else:
            todo_list_enable = False

        record_val = {
            'record_dict': record_dict,
            'darkmode': darkmode,
            'bookmark_panel': user.bookmark_panel,
            'pinned_sidebar': pinned_sidebar,
            'show_edit_mode': show_edit_mode,
            'is_admin': is_admin,
            'todo_list_enable': todo_list_enable,
            'prevent_auto_save': prevent_auto_save,
        }
        return record_val

    @http.route(['/get-favorite-apps'], type='json', auth='public')
    def get_favorite_apps(self, **kw):
        user_id = request.env.user
        app_list = []
        if user_id.app_ids:
            for app in user_id.app_ids:
                irmenu = request.env['ir.ui.menu'].sudo().search(
                    [('id', '=', app.app_id)])
                if irmenu:
                    app_dict = {
                        'name': app.name,
                        'app_id': app.app_id,
                        'app_xmlid': app.app_xmlid,
                        'app_actionid': app.app_actionid,
                        'line_id': app.id,
                        'use_icon': irmenu.use_icon,
                        'icon_class_name': irmenu.icon_class_name,
                        'icon_img': irmenu.icon_img,
                        'web_icon': irmenu.web_icon,
                        'web_icon_data': irmenu.web_icon_data,
                    }
                    app_list.append(app_dict)
            record_val = {
                'app_list': app_list,
            }
            return record_val
        else:
            return False

    @http.route(['/update-user-fav-apps'], type='json', auth='public')
    def update_favorite_apps(self, **kw):
        user_id = request.env.user
        user_id.sudo().write({
            'app_ids': [(0, 0, {
                'name': kw.get('app_name'),
                'app_id': kw.get('app_id'),
            })]
        })
        return True

    @http.route(['/remove-user-fav-apps'], type='json', auth='public')
    def remove_favorite_apps(self, **kw):
        user_id = request.env.user

        for line in user_id.app_ids:
            if line.app_id == str(kw.get('app_id')):
                user_id.sudo().write({
                    'app_ids': [(3, line.id)]
                })
        return True

    @http.route(['/get/active/menu'], type='json', auth='public')
    def get_active_menu_data(self, **kw):
        menu_items = []
        menu_records = request.env['ir.ui.menu'].search(
            [('parent_id', '=', False)])
        for menu in menu_records:
            menu_items.append({
                'menu_name': menu.complete_name,
                'menu_id': menu.id
            })
        return menu_items

    @http.route(['/get/appsearch/data'], type='json', auth='public')
    def get_appsearch_data(self, menuOption=None, **kw):
        menu_items = []
        menu_records = request.env['ir.ui.menu'].search(
            [('name', 'ilike', kw.get('searchvals'))], order='id asc')
        if menuOption:
            for record in menu_records:
                if record.parent_path:
                    parent_record = record.parent_path.split('/')
                    parent_record_id = parent_record[0]
                    if parent_record_id == menuOption:
                        if not record.child_id:
                            menu_items.append({
                                'name': record.complete_name,
                                'menu_id': record.id
                            })
        else:
            for record in menu_records:
                if not record.child_id:
                    menu_items.append({
                        'name': record.complete_name,
                        'menu_id': record.id,
                        'previous_menu_id': record.parent_id.id,
                        'action_id': record.action.id if record.action else None,
                    })
        return menu_items

    @http.route(['/get/tab/title/'], type='json', auth='public')
    def get_tab_title(self, **kw):
        company_id = request.env.company
        new_name = company_id.tab_name
        return new_name

    @http.route(['/get/active/lang'], type='json', auth='public')
    def get_active_lang(self, **kw):
        lang_records = request.env['res.lang'].sudo().search(
            [('active', '=', 'True')])
        lang_list = []
        for lang in lang_records:
            lang_list.append({
                'lang_name': lang.name,
                'lang_code': lang.code,
            })

        return lang_list

    @http.route(['/change/active/lang'], type='json', auth='public')
    def biz_change_active_lang(self, **kw):
        request.env.user.lang = kw.get('lang')
        return True

    @http.route([
        '/report/<converter>/<reportname>',
        '/report/<converter>/<reportname>/<docids>',
    ], type='http', auth='user', website=True, readonly=True)
    def report_routes(self, reportname, docids=None, converter=None, **data):
        report = request.env['ir.actions.report']
        context = dict(request.env.context)
        if docids:
            docids = [int(i) for i in docids.split(',') if i.isdigit()]
        if data.get('options'):
            data.update(json.loads(data.pop('options')))
        if data.get('context'):
            data['context'] = json.loads(data['context'])
            context.update(data['context'])
        if converter == 'html':
            html = report.sudo().with_user(SUPERUSER_ID).with_context(context)._render_qweb_html(reportname, docids, data=data)[0]
            return request.make_response(html)
        elif converter == 'pdf':
            if request.session.bg_color:
                pdf,format = report.sudo().with_user(SUPERUSER_ID).with_context(context)._render_qweb_pdf(reportname, docids, data=data)
                base64pdf = base64.b64encode(pdf)
                newbase64pdf = str(base64pdf).replace("b'","").replace("'","")
                return newbase64pdf
            else:
                pdf = report.with_context(context)._render_qweb_pdf(reportname, docids, data=data)[0]
                pdfhttpheaders = [('Content-Type', 'application/pdf'), ('Content-Length', len(pdf))]
                return request.make_response(pdf, headers=pdfhttpheaders)
        elif converter == 'text':
            text = report.with_context(context)._render_qweb_text(reportname, docids, data=data)[0]
            texthttpheaders = [('Content-Type', 'text/plain'), ('Content-Length', len(text))]
            return request.make_response(text, headers=texthttpheaders)
        else:
            raise werkzeug.exceptions.HTTPException(description='Converter %s not implemented.' % converter)
    
    @http.route('/text_color/label_color',type="json",auth="none")
    def text_color_label_color(self,**kw):
        generated_file_data = ''
        if 'options' in kw:
            if 'file_generator' and 'options' in kw['options']:
                check_method_name(kw['options']['file_generator'])
                file_generator = kw['options']['file_generator']
                options = json.loads(kw['options']['options'])
                uid = request.uid
                allowed_company_ids = [company_data['id'] for company_data in options.get('multi_company', [])]
                if not allowed_company_ids:
                    company_str = request.httprequest.cookies.get('cids', str(request.env.user.company_id.id))
                    allowed_company_ids = [int(str_id) for str_id in company_str.split(',')]
                report = request.env['account.report'].sudo().with_user(uid).with_context(allowed_company_ids=allowed_company_ids).browse(options['report_id'])
                btn_report_data = report.sudo().with_user(SUPERUSER_ID).dispatch_report_action(options, file_generator)
                pdf_report_name = btn_report_data['file_name'].split('.')[0]
                new_pdf_report_name = pdf_report_name.replace(" ","")
                base64xls = base64.b64encode(btn_report_data['file_content'])
                newbase64xls = str(base64xls).replace("b'","").replace("'","")
                generated_file_data  = {
                    'file_content':newbase64xls,
                    'file_type':'.'+str(btn_report_data['file_type']),
                    'file_name':new_pdf_report_name
                }    
            elif 'data' and 'context' in kw['options']:
                # Download pdf report 
                requestcontent = json.loads(kw['options']['data'])

                url, type_ = requestcontent[0], requestcontent[1]
                reportname = '???'
                context = kw['options']['context']

                if type_ in ['qweb-pdf', 'qweb-text']:
                    converter = 'pdf' if type_ == 'qweb-pdf' else 'text'
                    extension = '.pdf' if type_ == 'qweb-pdf' else '.txt'

                    pattern = '/report/pdf/' if type_ == 'qweb-pdf' else '/report/text/'
                    reportname = url.split(pattern)[1].split('?')[0]
                    docids = None
                    if '/' in reportname:
                        reportname, docids = reportname.split('/')
                    if docids:
                        # Generic report:
                        response = self.report_routes(reportname, docids=docids, converter=converter, context=context)
                    else:
                        # Particular report:
                        data = url_parse(url).decode_query(cls=dict)  # decoding the args represented in JSON
                        if 'context' in data:
                            context, data_context = json.loads(context or '{}'), json.loads(data.pop('context'))
                            context = json.dumps({**context, **data_context})
                        response = self.report_routes(reportname, converter=converter, context=context, **data)

                    report = request.env['ir.actions.report']._get_report_from_name(reportname)
                    file_name = report.name if report else 'Test'
                    pdf_report_name = file_name.replace(" ","")
                    filename = re.sub('[/]',"_",pdf_report_name)
                    if docids:
                        ids = [int(x) for x in docids.split(",") if x.isdigit()]
                        obj = request.env[report.model].browse(ids)
                        if report.print_report_name and not len(obj) > 1:
                            report_name = safe_eval(report.print_report_name, {'object': obj, 'time': time})
                            pdf_report_name = report_name.replace(" ","")
                            filename = re.sub('[/]',"_",pdf_report_name)
                    response.headers.add('Content-Disposition', content_disposition(filename))
                    generated_file_data = {
                        'file_content':response.data,
                        'file_type':extension,
                        'file_name':filename
                    }
                    return generated_file_data
                else:
                    return
            elif 'import_compat' in kw['options']['data']:
                # Download excel report from tree view
                params = json.loads(kw['options']['data'])
                model, fields, ids, domain, import_compat = \
                    operator.itemgetter('model', 'fields', 'ids', 'domain', 'import_compat')(params)

                Model = request.env[model].sudo().with_user(SUPERUSER_ID).with_context(import_compat=import_compat, **params.get('context', {}))
                if not Model._is_an_ordinary_table():
                    fields = [field for field in fields if field['name'] != 'id']

                field_names = [f['name'] for f in fields]
                if import_compat:
                    columns_headers = field_names
                else:
                    columns_headers = [val['label'].strip() for val in fields]
                groupby = params.get('groupby')
                model_description = request.env['ir.model']._get(model).name
                if not import_compat and groupby:
                    groupby_type = [Model._fields[x.split(':')[0]].type for x in groupby]
                    domain = [('id', 'in', ids)] if ids else domain
                    groups_data = Model.with_context(active_test=False).read_group(domain, ['__count'], groupby, lazy=False)

                    tree = GroupsTreeNode(Model, field_names, groupby, groupby_type)
                    for leaf in groups_data:
                        tree.insert_leaf(leaf)
                    with GroupExportXlsxWriter(fields, columns_headers, tree.count) as xlsx_writer:
                        x, y = 1, 0
                        for group_name, group in tree.children.items():
                            x, y = xlsx_writer.write_group(x, y, group_name, group)
                    base64xls = base64.b64encode(xlsx_writer.value)
                    newbase64xls = str(base64xls).replace("b'","").replace("'","")
                    
                    generated_file_data = {
                        'file_content':newbase64xls,
                        'file_type':'.xlsx',
                        'file_name':model_description
                    } 
                    
                else:
                    records = Model.sudo().browse(ids) if ids else Model.sudo().search(domain, offset=0, limit=False, order=False)
                    export_data = records.sudo().export_data(field_names).get('datas', [])
                    with ExportXlsxWriter(fields, columns_headers, len(export_data)) as xlsx_writer:
                        for row_index, row in enumerate(export_data):
                            for cell_index, cell_value in enumerate(row):
                                xlsx_writer.write_cell(row_index + 1, cell_index, cell_value)
                    base64xls = base64.b64encode(xlsx_writer.value)
                    newbase64xls = str(base64xls).replace("b'","").replace("'","")
                    generated_file_data = {
                        'file_content':newbase64xls,
                        'file_type':'.xlsx',
                        'file_name':model_description
                    }     
                    records = Model.sudo().browse(ids) if ids else Model.sudo().search(domain, offset=0, limit=False, order=False)
                    export_data = records.sudo().export_data(field_names).get('datas', [])
                    with ExportXlsxWriter(fields, columns_headers, len(export_data)) as xlsx_writer:
                        for row_index, row in enumerate(export_data):
                            for cell_index, cell_value in enumerate(row):
                                xlsx_writer.write_cell(row_index + 1, cell_index, cell_value)
                    base64xls = base64.b64encode(xlsx_writer.value)
                    newbase64xls = str(base64xls).replace("b'","").replace("'","")
                    generated_file_data = {
                        'file_content':newbase64xls,
                        'file_type':'.xlsx',
                        'file_name':model_description
                    }       
            elif 'col_group_headers' in kw['options']['data']:
                jdata = json.loads(kw['options']['data'])
                output = io.BytesIO()
                workbook = xlsxwriter.Workbook(output, {'in_memory': True})
                worksheet = workbook.add_worksheet(jdata['title'])

                header_bold = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#AAAAAA'})
                header_plain = workbook.add_format({'pattern': 1, 'bg_color': '#AAAAAA'})
                bold = workbook.add_format({'bold': True})

                measure_count = jdata['measure_count']
                origin_count = jdata['origin_count']

                # Step 1: writing col group headers
                col_group_headers = jdata['col_group_headers']

                # x,y: current coordinates
                # carry: queue containing cell information when a cell has a >= 2 height
                #      and the drawing code needs to add empty cells below
                x, y, carry = 1, 0, deque()
                for i, header_row in enumerate(col_group_headers):
                    worksheet.write(i, 0, '', header_plain)
                    for header in header_row:
                        while (carry and carry[0]['x'] == x):
                            cell = carry.popleft()
                            for j in range(measure_count * (2 * origin_count - 1)):
                                worksheet.write(y, x+j, '', header_plain)
                            if cell['height'] > 1:
                                carry.append({'x': x, 'height': cell['height'] - 1})
                            x = x + measure_count * (2 * origin_count - 1)
                        for j in range(header['width']):
                            worksheet.write(y, x + j, header['title'] if j == 0 else '', header_plain)
                        if header['height'] > 1:
                            carry.append({'x': x, 'height': header['height'] - 1})
                        x = x + header['width']
                    while (carry and carry[0]['x'] == x):
                        cell = carry.popleft()
                        for j in range(measure_count * (2 * origin_count - 1)):
                            worksheet.write(y, x+j, '', header_plain)
                        if cell['height'] > 1:
                            carry.append({'x': x, 'height': cell['height'] - 1})
                        x = x + measure_count * (2 * origin_count - 1)
                    x, y = 1, y + 1

                # Step 2: writing measure headers
                measure_headers = jdata['measure_headers']

                if measure_headers:
                    worksheet.write(y, 0, '', header_plain)
                    for measure in measure_headers:
                        style = header_bold if measure['is_bold'] else header_plain
                        worksheet.write(y, x, measure['title'], style)
                        for i in range(1, 2 * origin_count - 1):
                            worksheet.write(y, x+i, '', header_plain)
                        x = x + (2 * origin_count - 1)
                    x, y = 1, y + 1
                    # set minimum width of cells to 16 which is around 88px
                    worksheet.set_column(0, len(measure_headers), 16)

                # Step 3: writing origin headers
                origin_headers = jdata['origin_headers']

                if origin_headers:
                    worksheet.write(y, 0, '', header_plain)
                    for origin in origin_headers:
                        style = header_bold if origin['is_bold'] else header_plain
                        worksheet.write(y, x, origin['title'], style)
                        x = x + 1
                    y = y + 1

                # Step 4: writing data
                x = 0
                for row in jdata['rows']:
                    worksheet.write(y, x, row['indent'] * '     ' + ustr(row['title']), header_plain)
                    for cell in row['values']:
                        x = x + 1
                        if cell.get('is_bold', False):
                            worksheet.write(y, x, cell['value'], bold)
                        else:
                            worksheet.write(y, x, cell['value'])
                    x, y = 0, y + 1

                workbook.close()
                xlsx_data = output.getvalue()
                filename = osutil.clean_filename(_("Pivot %(title)s (%(model_name)s)", title=jdata['title'], model_name=jdata['model']))
                generated_file_data = {
                        'file_content':xlsx_data,
                        'file_type':'.xlsx',
                        'file_name':filename}    
        return generated_file_data   
    
    @http.route('/attach/get_data', type='json', auth="user")
    def download_attach_data(self,**kw):
        attach_id = kw.get('id')
        data = []
        if attach_id:
            attach_obj = request.env['ir.attachment'].browse(int(attach_id))
            if attach_obj:
                attach_type = mimetypes.guess_extension(attach_obj.mimetype)
                if attach_obj.name:
                    attach_list = attach_obj.name.split('.')
                    attachname = attach_list[0]
                else:
                    attachname = ''
                newbase64pdf = str(attach_obj.datas).replace("b'","").replace("'","")
                data = {
                    'pdf_data':newbase64pdf,
                    'attach_name':attachname,
                    'attach_type':attach_type
                }
        return data
    
    @http.route("/app/attachment/upload", methods=["POST"], type="http", auth="public",csrf=False)
    @add_guest_to_context
    def mail_attachment_upload_from_app(self, ufile, thread_id, thread_model, is_pending=False, **kwargs):
        thread = request.env[thread_model].search([("id", "=", thread_id)])
        if not thread:
            raise NotFound()
        if thread_model == "discuss.channel" and not thread.allow_public_upload and not request.env.user._is_internal():
            raise AccessError(_("You are not allowed to upload attachments on this channel."))
        vals = {
            "name": ufile.filename,
            "raw": ufile.read(),
            "res_id": int(thread_id),
            "res_model": thread_model,
        }
        if is_pending and is_pending != "false":
            # Add this point, the message related to the uploaded file does
            # not exist yet, so we use those placeholder values instead.
            vals.update(
                {
                    "res_id": 0,
                    "res_model": "mail.compose.message",
                }
            )
        if request.env.user.share:
            # Only generate the access token if absolutely necessary (= not for internal user).
            vals["access_token"] = request.env["ir.attachment"]._generate_access_token()
        try:
            # sudo: ir.attachment - posting a new attachment on an accessible thread
            attachment = request.env["ir.attachment"].sudo().create(vals)
            attachment._post_add_create(**kwargs)
            attachmentData = attachment._attachment_format()[0]
            if attachment.access_token:
                attachmentData["accessToken"] = attachment.access_token
        except AccessError:
            attachmentData = {"error": _("You are not allowed to upload an attachment here.")}
        return request.make_json_response(attachmentData)

    @http.route(['/active/dark/mode'], type='json', auth='public')
    def active_dark_mode(self, **kw):
        dark_mode = kw.get('dark_mode')
        backend_theme_config = request.env['backend.config'].sudo().search([])
        user = request.env.user
        if dark_mode == 'on':
            user.update({
                'dark_mode': True,
            })
            dark_mode = user.dark_mode
            return dark_mode
        elif dark_mode == 'off':
            user.update({
                'dark_mode': False,
            })
            dark_mode = user.dark_mode
            return dark_mode
    
    @http.route(['/update/bookmark/panel/show'], type='json', auth='public')
    def update_bookmark_panel_show(self, **kw):
        bookmark_panel = kw.get('bookmark_panel')
        user = request.env.user
        user.update({
            'bookmark_panel': bookmark_panel,
        })

    @http.route(['/sidebar/behavior/update'], type='json', auth='public')
    def sidebar_behavior(self, **kw):
        user = request.env.user
        sidebar_pinned = kw.get('sidebar_pinned')
        user.update({
            'vertical_sidebar_pinned': sidebar_pinned,
        })
        return True

    @http.route(['/get/dark/mode/data'], type='json', auth='public')
    def dark_mode_on(self, **kw):
        user = request.env.user
        dark_mode_value = user.dark_mode

        return dark_mode_value

    # SPIFFY MULTI TAB START
    @http.route(['/add/mutli/tab'], type='json', auth='public')
    def add_multi_tab(self, **kw):
        user = request.env.user
        # user.sudo().write({
        #     'multi_tab_ids': False,
        # })
        multi_tab_ids = user.multi_tab_ids.filtered(
            lambda mt: mt.name == kw.get('name'))
        if not multi_tab_ids:
            user.sudo().write({
                'multi_tab_ids': [(0, 0,  {
                    'name': kw.get('name'),
                    'url': kw.get('url'),
                    'actionId': kw.get('actionId'),
                    'menuId': kw.get('menuId'),
                    'menu_xmlid': kw.get('menu_xmlid'),
                })]
            })

        return True

    @http.route(['/get/mutli/tab'], type='json', auth='public')
    def get_multi_tab(self, **kw):
        obj = request.env['biz.multi.tab']
        user = request.env.user
        if user.multi_tab_ids:
            record_dict = user.multi_tab_ids.sudo().read(set(obj._fields))
            return record_dict
        else:
            return False

    @http.route(['/remove/multi/tab'], type='json', auth='public')
    def remove_multi_tab(self, **kw):
        multi_tab = request.env['biz.multi.tab'].sudo().search(
            [('id', '=', kw.get('multi_tab_id'))])
        multi_tab.unlink()
        user = request.env.user
        multi_tab_count = len(user.multi_tab_ids)
        values = {
            'removeTab': True,
            'multi_tab_count': multi_tab_count,
        }
        return values

    @http.route(['/update/tab/details'], type='json', auth='public')
    def update_tabaction(self, **kw):
        tabId = kw.get('tabId')
        TabTitle = kw.get('TabTitle')
        url = kw.get('url')
        ActionId = kw.get('ActionId')
        menu_xmlid = kw.get('menu_xmlid')

        multi_tab = request.env['biz.multi.tab'].sudo().search(
            [('id', '=', tabId)])
        if multi_tab:
            multi_tab.sudo().write({
                'name': TabTitle or multi_tab.name,
                'url': url or multi_tab.url,
                'actionId': ActionId or multi_tab.ActionId,
                'menu_xmlid': menu_xmlid or multi_tab.menu_xmlid,
            })
        return True
    # SPIFFY MULTI TAB END

    @http.route(['/add/bookmark/link'], type='json', auth='public')
    def add_bookmark_link(self, **kw):
        user = request.env.user
        bookmark_ids = user.bookmark_ids.filtered(
            lambda b: b.name == kw.get('name'))
        if not bookmark_ids:
            user.sudo().write({
                'bookmark_ids': [(0, 0,  {
                    'name': kw.get('name'),
                    'url': kw.get('url'),
                    'title': kw.get('title'),
                })]
            })

        return True

    @http.route(['/update/bookmark/link'], type='json', auth='public')
    def update_bookmark_link(self, **kw):
        bookmark = request.env['bookmark.link'].sudo().search(
            [('id', '=', kw.get('bookmark_id'))])
        updated_bookmark = bookmark.update({
            'name': kw.get('bookmark_name'),
            'title': kw.get('bookmark_title'),
        })
        return True

    @http.route(['/remove/bookmark/link'], type='json', auth='public')
    def remove_bookmark_link(self, **kw):
        bookmark = request.env['bookmark.link'].sudo().search(
            [('id', '=', kw.get('bookmark_id'))])
        bookmark.unlink()
        return True

    @http.route(['/get/bookmark/link'], type='json', auth='public')
    def get_bookmark_link(self, **kw):
        obj = request.env['bookmark.link']
        user = request.env.user
        record_dict = user.bookmark_ids.sudo().read(set(obj._fields))
        return record_dict

    @http.route(['/update/chatter/position'], type='json', auth='public')
    def update_chatter_position(self, **kw):
        current_user = request.env.user
        if not kw:
            if current_user.backend_theme_config:
                # current_user.backend_theme_config.sudo().update(config_vals)
                return current_user.backend_theme_config.chatter_position
            else:
                return False
        config_vals = {}

        config_vals.update({
            'chatter_position': kw.get('chatter_position')
        })
        if current_user.backend_theme_config:
            current_user.backend_theme_config.sudo().update(config_vals)
        else:
            backend_config_record = request.env['backend.config'].sudo().create(
                config_vals)
            current_user.sudo().write({
                'backend_theme_config': backend_config_record.id
            })
        return True


    @http.route(['/get/attachment/data'], type='json', auth='public')
    def get_attachment_data(self, **kw):
        rec_ids = kw.get('rec_ids')
        for rec in rec_ids:
            if isinstance(rec, str):
                rec_ids.remove(rec)
        if kw.get('model') and rec_ids:
            # FOR DATA SPEED ISSUE; SEARCH ATTACHMENT DATA WITH SQL QUERY
            attachments = request.env['ir.attachment'].sudo().search([
                ('res_model', '=', kw.get('model')), ('res_id', 'in', rec_ids)
            ])
            attachment_data = []
            attachment_res_id_set = set()
            for attachment in attachments:
                attachment_res_id_set.add(attachment.res_id)
            dict = {}
            for res_id in attachment_res_id_set:
                filtered_attachment_record = attachments.filtered(
                    lambda attachment: attachment.res_id == res_id)
                for fac in filtered_attachment_record:
                    if dict.get(res_id):
                        dict[res_id].append({
                            'attachment_id': fac.id,
                            'attachment_mimetype': fac.mimetype,
                            'attachment_name': fac.name,
                        })
                    else:
                        dict[res_id] = [{
                            'attachment_id': fac.id,
                            'attachment_mimetype': fac.mimetype,
                            'attachment_name': fac.name,
                        }]
            attachment_data.append(dict)
            return attachment_data

    @http.route(['/get/irmenu/icondata'], type='json', auth='public')
    def get_irmenu_icondata(self, **kw):
        irmenuobj = request.env['ir.ui.menu']
        spiffy_app_group = request.env['spiffy.app.group'].sudo().search_read([], fields=['id', 'name', 'group_menu_icon', 'sequence'])
        spiffy_app_group = sorted(spiffy_app_group, key=lambda group: group['sequence'])

        irmenu = request.env['ir.ui.menu'].sudo().search([('id', 'in', kw.get('menu_ids'))])

        app_menu_dict = {}
        processed_spiffy_app_group_ids = set()

        menu_data = []
        groups = request.env['spiffy.app.group'].sudo().search([])

        for group in groups:
            group_data = {
                'id': group.id,
                'name': group.name,
                'menus': []
            }

            for menu in group.group_menu_list_ids:
                group_data['menus'].append({
                    'id': menu.id,
                    'name': menu.name,
                    'icon_class_name': menu.icon_class_name or "",
                    'use_icon': menu.use_icon,
                    'icon_img': menu.icon_img.decode('utf-8') if menu.icon_img else "",
                })

            menu_data.append(group_data)
        menu_list = []
        for menu in irmenu:
            if not menu.spiffy_app_group_id:
                menu_list.append(menu.id)
        app_menu_list = str(menu_list) if menu_list else "[]"
        for menu in irmenu:
            if menu.spiffy_app_group_id:
                spiffy_app_group_id = menu.spiffy_app_group_id[0].id

                if spiffy_app_group_id not in processed_spiffy_app_group_ids:
                    spiffy_app_group_data = request.env['spiffy.app.group'].sudo().search_read(
                        [('id', '=', spiffy_app_group_id)], 
                        fields=['id', 'name', 'sequence', 'group_menu_icon', 'group_menu_list_ids', 'use_group_icon', 'group_icon_class_name']
                    )
                    if spiffy_app_group_data:
                        app_menu_dict.setdefault('spiffy_app_group', []).append(spiffy_app_group_data[0])
                        processed_spiffy_app_group_ids.add(spiffy_app_group_id)
            
            menu_dict = menu.read(set(irmenuobj._fields))
            app_menu_dict[menu.id] = menu_dict
            [item.update({'app_menu_list': app_menu_list}) for item in app_menu_dict[menu.id] if 'app_menu_list' in item]
        
        if 'spiffy_app_group' in app_menu_dict:
            app_menu_dict['spiffy_app_group'] = sorted(app_menu_dict['spiffy_app_group'], key=lambda group: group['sequence'])
        
        return app_menu_dict

    # TO DO LIST CONTROLLERS
    @http.route(['/show/user/todo/list/'], type='http', auth='public', sitemap=False)
    def show_user_todo_list(self, **kw):
        company = request.env.company
        user = request.env.user

        values = {}
        user_tz_offset = user.tz_offset
        user_tz_offset_time = datetime.datetime.strptime(user_tz_offset, '%z').utcoffset()
        today_date = datetime.datetime.now()
        today_date_with_offset = datetime.datetime.now() + user_tz_offset_time

        values.update({
            'user': user.sudo(),
            'today_date': today_date_with_offset,
            'user_tz_offset_time': user_tz_offset_time,
        })

        response = request.render("spiffy_theme_backend.to_do_list_template", values)

        return response

    @http.route(['/create/todo'], type='json', auth='public')
    def create_todo(self, **kw):
        user_id = kw.get('user_id', None)
        note_title = kw.get('note_title', None)
        note_description = kw.get('note_description', None)
        is_update = kw.get('is_update')
        note_id = kw.get('note_id', None)
        note_pallet = kw.get('note_pallet', None)

        user = request.env.user

        if user_id and (note_title or note_description):
            user_tz_offset = user.tz_offset
            user_tz_offset_time = datetime.datetime.strptime(user_tz_offset, '%z')

            todo_obj = request.env['todo.list'].sudo()

            if is_update:
                todo_record = todo_obj.browse(int(note_id))
                todo_record.update({
                    'name': note_title,
                    'description': note_description,
                    'note_color_pallet': note_pallet,
                })
            else:
                todo_record = todo_obj.create({
                    'user_id': int(user_id),
                    'name': note_title,
                    'description': note_description,
                    'note_color_pallet': note_pallet,
                })

            user_tz_offset = user.tz_offset
            user_tz_offset_time = datetime.datetime.strptime(user_tz_offset, '%z').utcoffset()
            today_date = datetime.datetime.now()
            today_date_with_offset = datetime.datetime.now() + user_tz_offset_time

            note_content = request.env['ir.ui.view']._render_template(
                "spiffy_theme_backend.to_do_list_content_template", {
                    'note': todo_record,
                    'today_date': today_date_with_offset,
                    'user_tz_offset_time': user_tz_offset_time,
                }
            )

            return note_content

    @http.route(['/delete/todo'], type='json', auth='public')
    def delete_todo(self, **kw):
        note_id = kw.get('noteID', None)
        if note_id:
            todo_obj = request.env['todo.list'].sudo()
            todo_record = todo_obj.browse(note_id)
            todo_record.unlink()
            return True
        else:
            return False
        
    @http.route('/theme_color/parameter_check', type='json', auth="none")
    def ThemecolorParameterCheck(self, uid,**post):
        module_obj = request.env['ir.module.module'].sudo().search([('name','=','spiffy_theme_backend'),('state','=','installed')])
        if module_obj:
            if post.get('color_data'):
                color_data = post.get('color_data')
                color_id = post.get('color_id')
                theme_color = post.get('theme_color')
                view_obj = request.env['ir.ui.view'].sudo().search(['|',('key','=',color_data),('key','=',theme_color)])
                if view_obj:
                    view_color = view_obj.arch.find(color_id)
                    if view_color == -1:
                        return {
                            'code':201,
                            'message':'Spiffy Theme is not installed in your Odoo'
                            }
                else:
                    return {
                            'code':201,
                            'message':'Spiffy Theme is not installed in your Odoo'
                            }
        else:
            return {
                    'code':201,
                    'message':'Spiffy Theme is not installed in your Odoo'
                    }
            
        request.session.bg_color = True
        if uid == "null" and request.session.pre_uid:
            uid = request.session.pre_uid
            url = request.env(user=uid)['res.users'].browse(uid)._mfa_url()
            csrf_token = request.csrf_token()
            url_dict = {"code":202,"2fa_required":True,"url":url,"csrf_token":csrf_token,"redirect":"/web?"}
            return url_dict
        else:
            if 'device_token' and 'device_name' in post:
                device_token = post.get('device_token')
                device_name = post.get('device_name')
                if device_token and device_name:
                    user_obj = request.env['mail.firebase'].sudo().search([('user_id','=',int(uid)),('token','=',device_token)])
                    if not user_obj:
                        request.env['mail.firebase'].sudo().create({'user_id':int(uid),'os':device_name,'token':device_token})
        return {'code':200, 'message':'Data match successfully'}

class Dataset(primary_colorDataset):
    @http.route(['/web/dataset/call_kw', '/web/dataset/call_kw/<path:path>'], type='json', auth="user")
    def call_kw(self, model, method, args, kwargs, path=None):
        if type(args) == str:
            args = literal_eval(args)
        if type(kwargs) == str:
            kwargs = literal_eval(kwargs)
        res = super(Dataset, self).call_kw(model,method,args,kwargs,path)
        return res

class WebManifest(SpiffyWebManifest):
    def _icon_path(self):
        return 'spiffy_theme_backend/static/src/image/loader_2.gif'
    
    @http.route('/web/offline', type='http', auth='public', methods=['GET'])
    def offline(self):
        """ Returns the offline page delivered by the service worker """
        return request.render('web.webclient_offline', {
            'odoo_icon': base64.b64encode(file_open(self._icon_path(), 'rb').read())
        })
        
class AuthHome(Home):
    @http.route(
        '/web/login/totp',
        type='http', auth='public', methods=['GET', 'POST'], sitemap=False,
        website=True, multilang=False # website breaks the login layout...
    )
    def web_totp(self, redirect=None, **kwargs):
        if request.session.uid:
            return request.redirect(self._login_redirect(request.session.uid, redirect=redirect))

        if not request.session.pre_uid:
            return request.redirect('/web/login')

        error = None

        user = request.env['res.users'].browse(request.session.pre_uid)
        if user and request.httprequest.method == 'GET':
            cookies = request.httprequest.cookies
            key = cookies.get(TRUSTED_DEVICE_COOKIE)
            if key:
                user_match = request.env['auth_totp.device']._check_credentials_for_uid(
                    scope="browser", key=key, uid=user.id)
                if user_match:
                    request.session.finalize(request.env)
                    return request.redirect(self._login_redirect(request.session.uid, redirect=redirect))

        elif user and request.httprequest.method == 'POST' and kwargs.get('totp_token'):
            try:
                with user._assert_can_auth(user=user.id):
                    user._totp_check(int(re.sub(r'\s', '', kwargs['totp_token'])))
            except AccessDenied as e:
                if 'tool_color_id' in kwargs:
                    error = str(e)
                    value = {'code':201,'error':error}
                    new_value  = json.dumps(value)
                    return new_value
                else:
                    error = str(e)
            except ValueError:
                if 'tool_color_id' in kwargs:
                    value = {'code':201,'error':_("Invalid authentication code format.")}
                    new_value  = json.dumps(value)
                    return new_value
                else:
                    error = _("Invalid authentication code format.")
            else:
                request.session.finalize(request.env)
                request.update_env(user=request.session.uid)
                request.update_context(**request.session.context)
                response = request.redirect(self._login_redirect(request.session.uid, redirect=redirect))
                if kwargs.get('remember'):
                    name = _("%(browser)s on %(platform)s",
                        browser=request.httprequest.user_agent.browser.capitalize(),
                        platform=request.httprequest.user_agent.platform.capitalize(),
                    )

                    if request.geoip.city.name:
                        name += f" ({request.geoip.city.name}, {request.geoip.country_name})"

                    key = request.env['auth_totp.device']._generate("browser", name)
                    response.set_cookie(
                        key=TRUSTED_DEVICE_COOKIE,
                        value=key,
                        max_age=TRUSTED_DEVICE_AGE,
                        httponly=True,
                        samesite='Lax'
                    )
                # Crapy workaround for unupdatable Odoo Mobile App iOS (Thanks Apple :@)
                request.session.touch()
                if 'tool_color_id' in kwargs:
                    value = {'code':200,'message':"Authentication Success","is_2fa_login":True}
                    new_value  = json.dumps(value)
                    uid = request.session.uid
                    device_token = kwargs.get('device_token')
                    device_name = kwargs.get('tool_color_id')
                    if device_name and device_token:
                        user_obj = request.env['mail.firebase'].search([('user_id','=',int(uid)),('token','=',device_token)])
                        if not user_obj:
                            request.env['mail.firebase'].create({'user_id':int(uid),'os':device_name,'token':device_token})
                    return new_value
                return response

        # Crapy workaround for unupdatable Odoo Mobile App iOS (Thanks Apple :@)
        request.session.touch()
        return request.render('auth_totp.auth_totp_form', {
            'user': user,
            'error': error,
            'redirect': redirect,
        })
    
class CustomExportXlsxWriter(ExportXlsxWriter):
    def __init__(self, fields, columns_headers, row_count):
        self.fields = fields
        self.columns_headers = columns_headers
        self.output = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(self.output, {'in_memory': True})
        self.header_style = self.workbook.add_format({'bold': True})
        self.date_style = self.workbook.add_format({'text_wrap': True, 'num_format': 'yyyy-mm-dd'})
        self.datetime_style = self.workbook.add_format({'text_wrap': True, 'num_format': 'yyyy-mm-dd hh:mm:ss'})
        self.base_style = self.workbook.add_format({'text_wrap': True})
        # FIXME: Should depends of the field digits
        self.float_style = self.workbook.add_format({'text_wrap': True, 'num_format': '#,##0.00'})

        # FIXME: Should depends of the currency field for each row (also maybe add the currency symbol)
        decimal_places = request.env['res.currency'].sudo()._read_group([], aggregates=['decimal_places:max'])[0][0]
        self.monetary_style = self.workbook.add_format({'text_wrap': True, 'num_format': f'#,##0.{(decimal_places or 2) * "0"}'})

        header_bold_props = {'text_wrap': True, 'bold': True, 'bg_color': '#e9ecef'}
        self.header_bold_style = self.workbook.add_format(header_bold_props)
        self.header_bold_style_float = self.workbook.add_format(dict(**header_bold_props, num_format='#,##0.00'))
        self.header_bold_style_monetary = self.workbook.add_format(dict(**header_bold_props, num_format=f'#,##0.{(decimal_places or 2) * "0"}'))

        self.worksheet = self.workbook.add_worksheet()
        self.value = False

        if row_count > self.worksheet.xls_rowmax:
            raise UserError(request.env._('There are too many rows (%(count)s rows, limit: %(limit)s) to export as Excel 2007-2013 (.xlsx) format. Consider splitting the export.', count=row_count, limit=self.worksheet.xls_rowmax))
        
ExportXlsxWriter.__init__ = CustomExportXlsxWriter.__init__