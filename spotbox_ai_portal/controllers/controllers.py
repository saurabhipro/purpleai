import base64
import json
import math
import re

from werkzeug import urls

from odoo import http, tools, _, SUPERUSER_ID
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import content_disposition, Controller, request, route
from odoo.tools import consteq

class SpotboxAiPortal(Controller):
    def _prepare_portal_layout_values(self):
        """Values for /my/* templates rendering.

        Does not include the record counts.
        """
        sales_user_sudo = request.env['res.users']
        partner_sudo = request.env.user.partner_id
        if partner_sudo.user_id and not partner_sudo.user_id._is_public():
            sales_user_sudo = partner_sudo.user_id
        else:
            fallback_sales_user = partner_sudo.commercial_partner_id.user_id
            if fallback_sales_user and not fallback_sales_user._is_public():
                sales_user_sudo = fallback_sales_user

        return {
            'sales_user': sales_user_sudo,
            'page_name': 'home',
        }

    @route(['/', '/my-home'], type='http', auth="user", website=True)
    def customer_home(self, **kw):
        values = self._prepare_portal_layout_values()
        values['partner_id'] = request.env.user.partner_id.id
        values['page_name'] = 'My Details'

        return request.render("spotbox_ai_portal.spotboxai_portal_my_home", values)

    

    # API FOR THE RES PARTNER
    # List
    @http.route(['/my/contact-list/<int:partner_id>'], type='http', auth="user", website=True)
    def customer_own_res_partner_list(self, partner_id, **post):
        if request.env.user.partner_id.id == partner_id:
            if request.httprequest.method == 'GET':
                partners = request.env['res.partner'].sudo().search([('email','=',request.env.user.partner_id.email)]) 
                values = {
                    'partners':partners,
                    'partner_id':partner_id,
                    'page_name':'customer_own_res_partner_list',
                }
                return request.render("spotbox_ai_portal.portal_my_contacts_tree_view", values)
        return request.render("http_routing.404")
    
    # Create
    @http.route(['/my/contact-create/<int:partner_id>'], type='http', auth="user", website=True)
    def customer_own_res_partner_create(self, partner_id, **post):
        
        if request.env.user.partner_id.id != partner_id:
            return request.render("http_routing.404")
        
        if request.httprequest.method == 'GET':
            country_ids = request.env['res.country'].sudo().search([])        
            states = request.env['res.country.state'].sudo().search([])
            values = {
                'countries':country_ids,
                'states':states,
                'page_name': 'customer_own_res_partner_create',
                'partner_id':partner_id,
            }
            return request.render("spotbox_ai_portal.portal_my_contacts_create", values)
        
        elif request.httprequest.method == 'POST':
                company_type = None
                if post['company_type'] == 'person':
                    company_type = 'person'
                elif post['company_type'] == 'company':
                    company_type = 'company'

                vals = {     
                    'company_type' : company_type,
                    'name' : post['name'],
                    'email' : request.env.user.partner_id.email,
                    'phone' : post['phone'],
                    'mobile' : post['mobile'],
                    'street' : post['street'],
                    'street2' : post['street2'],
                    'city' : post['city'],
                    'zip' : post['zipcode'],
                    'state_id' : int(post['state_id']) if post['state_id'] else None,
                    'country_id' : int(post['country_id']) if post['country_id'] else None,
                    }
                partner = request.env['res.partner'].sudo().create(vals)
                return request.redirect(f"/my/contact-list/{partner_id}")
                
    # Edit
    @http.route(['/my/contact-edit/<int:partner_id>/<int:edit_partner_id>'], type='http', auth="user", website=True)
    def customer_own_details(self, partner_id, edit_partner_id, **post ):   
        edit_partner_model = request.env['res.partner'].sudo().search([('id','=',edit_partner_id),('email','=',request.env.user.partner_id.email)])
        if request.env.user.partner_id.id != partner_id or not edit_partner_model:
            return request.render("http_routing.404")
        if request.httprequest.method == 'POST':     
            partner = request.env['res.partner'].sudo().browse(edit_partner_id)
            company_type = None
            if post['company_type'] == 'person':
                company_type = 'person'
            elif post['company_type'] == 'company':
                company_type = 'company'

            vals = {     
                'company_type' : company_type,
                'name' : post['name'],
                'phone' : post['phone'],
                'mobile' : post['mobile'],
                'street' : post['street'],
                'street2' : post['street2'],
                'city' : post['city'],
                'zip' : post['zipcode'],
                'state_id' : int(post['state_id']) if post['state_id'] else None,
                'country_id' : int(post['country_id'])if post['country_id'] else None,
                }

            partner.write(vals)
            return request.redirect(f'/my/contact-list/{partner_id}')
        else:
            partner_details = request.env['res.partner'].sudo().browse(edit_partner_id)
            country_ids = request.env['res.country'].sudo().search([])        
            states = request.env['res.country.state'].sudo().search([])
            partner_details = {
                'partner':partner_details,
                'countries':country_ids,
                'states':states,
                'page_name': 'customer_own_details',
                'partner_id' : partner_id,
                'edit_partner_id':edit_partner_id,
            }

            return request.render("spotbox_ai_portal.portal_my_contacts_and_address", partner_details)
        

    # Res partner child create and edit 
    @http.route(['/my/contact-edit/<int:partner_id>/<int:edit_partner_id>/child_id', '/my/contact-edit/<int:partner_id>/<int:edit_partner_id>/child_id/<int:child_partner_id>'], type='http', auth="user", website=True)
    def customer_own_child_details(self, partner_id, edit_partner_id, child_partner_id=None, **post):   
        edit_partner_model = request.env['res.partner'].sudo().search([('id','=',edit_partner_id),('email','=',request.env.user.partner_id.email)])
        if request.env.user.partner_id.id != partner_id or not edit_partner_model:
            return request.render("http_routing.404")

        if request.httprequest.method == 'POST':
            partner = request.env['res.partner'].sudo().browse(edit_partner_id)
            if not partner:
                return "partner does not exist"
            add_type = None
            if post['address_type'] == 'contact':
                add_type = 'contact'
            elif post['address_type'] == 'invoice':
                add_type = 'invoice'
            elif post['address_type'] == 'delivery':
                add_type = 'delivery'
            else:
                add_type = 'other'
            vals = {     
                    'type' : add_type,
                    'name' : post['name'],
                    'email' : post['email'],
                    'phone' : post['phone'],
                    'mobile' : post['mobile'],
                    'street' : post['street'],
                    'street2' : post['street2'],
                    'city' : post['city'],
                    'zip' : post['zipcode'],
                    'state_id' : int(post.get('state_id')),
                    'country_id' : int(post.get('country_id')),
                    
                    }

            # Update partner child line
            if edit_partner_id and child_partner_id:
                partner.sudo().write({'child_ids': [(1, child_partner_id, vals)]})
            # create partner child line
            else:
                partner.sudo().write({'child_ids':[(0, 0, (vals))]})
            return request.redirect(f'/my/contact-edit/{partner_id}/{edit_partner_id}')

        country_ids = request.env['res.country'].sudo().search([])        
        states = request.env['res.country.state'].sudo().search([])
        # Show value if record exist
        if  partner_id and request.httprequest.method == 'GET' and child_partner_id:
            child_partner = request.env['res.partner'].sudo().browse(child_partner_id)
            partner_details = {
                'countries':country_ids,
                'states':states,
                'child_partner':child_partner,
                'page_name': 'customer_own_child_details',
                'partner_id':partner_id,
                'edit_partner_id':edit_partner_id
            }
        # blank form
        else:
            partner_details = {
                'countries':country_ids,
                'states':states,
                'child_partner':None,
                'page_name': 'customer_own_child_details',
                'partner_id':partner_id,
                'edit_partner_id':edit_partner_id,
            }
        return request.render("spotbox_ai_portal.partner_child_ids_form_template", partner_details)

    # API FOR THE SALE ORDER
    # Create
    @http.route(['/my/order/<int:partner_id>/<int:edit_partner_id>'], type='http', auth="user", website=True)
    def customer_own_sale_order_details(self, partner_id, edit_partner_id, **post):
        
        edit_partner_model = request.env['res.partner'].sudo().search([('id','=',edit_partner_id),('email','=',request.env.user.partner_id.email)])
        if request.env.user.partner_id.id != partner_id or not edit_partner_model:
            return request.render("http_routing.404")


        if request.httprequest.method == 'POST': 
            product_ids = request.httprequest.form.getlist('pol_product_id[]')
            quantities = request.httprequest.form.getlist('pol_product_qty[]')

            product_quantity_dict = dict(zip(product_ids, quantities))
            child_ids = request.env['res.partner'].sudo().browse(edit_partner_id)
            partner_invoice_id = [child_invoice.id for child_invoice in child_ids if child_invoice.type == 'invoice'] or edit_partner_id
            partner_shipping_id = [child_invoice.id for child_invoice in child_ids if child_invoice.type == 'delivery'] or edit_partner_id
            
            vals = {
                'state': 'draft',
                'partner_id': edit_partner_id,
                'partner_invoice_id': partner_invoice_id,
                'partner_shipping_id': partner_shipping_id,
            }
            sale_order = request.env['sale.order'].sudo().create(vals)
            for product_id, qty in product_quantity_dict.items():
                product = request.env['product.product'].sudo().browse(int(product_id))
                if product:
                    request.env['sale.order.line'].sudo().create({
                        'order_id': sale_order.id, 
                        'product_id': product.id, 
                        'product_uom_qty': float(qty),  
                        'product_uom': product.uom_id.id, 
                        'price_unit': product.list_price, 
                    })
            return request.redirect(f'my/order-list/{partner_id}/{edit_partner_id}')
        else:
            partner_details = request.env['res.partner'].sudo().browse(edit_partner_id)
            portal_order_lines = request.env['portal.order.line'].sudo().search([('active','=',True)], order="sequence")
            
            partner_details = {
                'partner': partner_details,
                'portal_order_lines':portal_order_lines,
                'page_name':'customer_own_sale_order_details',
                'partner_id':partner_id,
                'edit_partner_id':edit_partner_id,
            }
            return request.render("spotbox_ai_portal.portal_my_orders_and_address", partner_details)
    

    # List view all and partner wise
    @http.route(['/my/order-list/<int:partner_id>/<int:edit_partner_id>', '/my/order-list-all/<int:partner_id>'], type='http', auth="user", website=True)
    def customer_own_sale_order_list(self, partner_id, edit_partner_id=None,**post):
        if edit_partner_id:
            edit_partner_model = request.env['res.partner'].sudo().search([('id','=',edit_partner_id),('email','=',request.env.user.partner_id.email)])
            if request.env.user.partner_id.id != partner_id or not edit_partner_model:
                return request.render("http_routing.404")
        else:
            edit_partner_model = request.env['res.partner'].sudo().search([('id','=',partner_id),('email','=',request.env.user.partner_id.email)])
            if request.env.user.partner_id.id != partner_id or not edit_partner_model:
                return request.render("http_routing.404")

        
        if request.httprequest.method == 'GET':
            all_partner_order = request.env['res.partner'].sudo().search([('email','=',request.env.user.partner_id.email)])
            sale_orders = request.env['sale.order'].sudo().search([('partner_id','in',all_partner_order.ids)]) 
            if edit_partner_id:
                all_partner_order = request.env['res.partner'].sudo().search([('email','=',request.env.user.partner_id.email),('id','=',edit_partner_id)])
                sale_orders = request.env['sale.order'].sudo().search([('partner_id','in',all_partner_order.ids)])
                values = {
                        'sale_orders':sale_orders,
                        'edit_partner_id':edit_partner_id,
                        'partner_id':partner_id,
                        'page_name':'customer_own_sale_order_list',
                    }

            
            values = {
                'sale_orders':sale_orders,
                'edit_partner_id':edit_partner_id,
                'partner_id':partner_id,
                'page_name':'customer_own_sale_order_list_all',

            }
            return request.render("spotbox_ai_portal.portal_my_order_tree_view", values)
        
    # Edit
    @http.route(['/my/order-edit/<int:partner_id>/<int:edit_partner_id>/<int:order_id>', '/my/order-list-all/order-edit/<int:partner_id>/<int:edit_partner_id>/<int:order_id>'], type='http', auth="user", website=True)
    def customer_own_sale_order_edit(self, partner_id, order_id, edit_partner_id=None, **post):
        
        edit_partner_model = request.env['res.partner'].sudo().search([('id','=',edit_partner_id),('email','=',request.env.user.partner_id.email)])
        check_sale_order = request.env['sale.order'].sudo().search([('id','=',order_id),('partner_id','=',edit_partner_model.id)])
        if request.env.user.partner_id.id != partner_id or not edit_partner_model or not check_sale_order:
            return request.render("http_routing.404")
        
        sale_order = request.env['sale.order'].sudo().search([('id', '=', order_id), ('partner_id', '=', edit_partner_id)], limit=1)
        if sale_order:
            if request.httprequest.method == 'POST':
                product_ids = request.httprequest.form.getlist('pol_product_id[]')
                quantities = request.httprequest.form.getlist('pol_product_qty[]')
                product_quantity_dict = dict(zip(product_ids, quantities))
                
                for product_id, qty in product_quantity_dict.items():
                    product = request.env['product.product'].sudo().browse(int(product_id))
                    
                    if product:
                        order_line = request.env['sale.order.line'].sudo().search([
                            ('order_id', '=', sale_order.id),
                            ('product_id', '=', product.id)
                        ], limit=1)

                        if order_line:
                            order_line.write({
                                'product_uom_qty': float(qty) if qty else 0.0,
                                'price_unit': product.list_price,
                            })
                return request.redirect(f"/my/order-list/{partner_id}/{edit_partner_id}")
        
        if request.httprequest.method == 'GET':
            values = {
                'sale_order':sale_order,
                'page_name':'customer_own_sale_order_edit',
                'partner_id':partner_id,
                'edit_partner_id':edit_partner_id,
            }

            if '/my/order-list-all/' in request.httprequest.path:
                values['page_name'] = 'customer_own_sale_order_edit_all'
            
            return request.render("spotbox_ai_portal.portal_edit_my_order_form", values)



from odoo.addons.portal.controllers.portal import CustomerPortal

class InheritedControllerClass(CustomerPortal):
    @route(['/my/orders', '/my/invoices', '/my/projects', '/my/tasks',], type='http', auth="user", website=True)
    def home_hide(self, **kw):
        values = self._prepare_portal_layout_values()
        return request.render("http_routing.404", values)
    
    @route(['/my', '/my/home'], type='http', auth="user", website=True)
    def home(self, **kw):
        values = self._prepare_portal_layout_values()
        values['partner_id'] = request.env.user.partner_id.id
        return request.render("spotbox_ai_portal.spotboxai_portal_my_home", values)
    

