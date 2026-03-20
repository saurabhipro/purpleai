# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
# Developed by Bizople Solutions Pvt. Ltd.

import base64
from odoo.tools.misc import file_path
from odoo import api, fields, models, tools, _

class BackendConfig(models.Model):
	_name = 'backend.config'
	_description = "Configurator Backend Theme"

	def _default_app_drawer_bg_image(self):
		image_path = file_path('spiffy_theme_backend/static/description/app-drawer-bg-image.png')
		with tools.file_open(image_path, 'rb') as f:
			return base64.b64encode(f.read())

	def _default_vertical_mini_bg_image_one(self):
		image_path = file_path('spiffy_theme_backend/static/description/top-menu-v2-bg1.jpg')
		with tools.file_open(image_path, 'rb') as f:
			return base64.b64encode(f.read())

	def _default_vertical_mini_bg_image_two(self):
		image_path = file_path('spiffy_theme_backend/static/description/top-menu-v2-bg2.jpg')
		with tools.file_open(image_path, 'rb') as f:
			return base64.b64encode(f.read())

	def _default_vertical_mini_bg_image_three(self):
		image_path = file_path('spiffy_theme_backend/static/description/top-menu-v2-bg3.jpg')
		with tools.file_open(image_path, 'rb') as f:
			return base64.b64encode(f.read())

	def _default_vertical_mini_bg_image_four(self):
		image_path = file_path('spiffy_theme_backend/static/description/top-menu-v2-bg4.jpg')
		with tools.file_open(image_path, 'rb') as f:
			return base64.b64encode(f.read())
	
	def _default_menu_bg_image(self):
		image_path = file_path('spiffy_theme_backend/static/description/header_vertical_mini.svg')
		with tools.file_open(image_path, 'rb') as f:
			return base64.b64encode(f.read())

	use_custom_colors = fields.Boolean(string="Use Custom Colors")
	use_custom_drawer_color = fields.Boolean(string="Use Custom Drawer Colors")

	tree_form_split_view = fields.Boolean(string="Tree Form Split View")

	color_pallet = fields.Selection([
		('pallet_1', 'Color Pallet 1'),
		('pallet_2', 'Color Pallet 2'),
		('pallet_3', 'Color Pallet 3'),
		('pallet_4', 'Color Pallet 4'),
		('pallet_5', 'Color Pallet 5'),
		('pallet_6', 'Color Pallet 6'),
		('pallet_7', 'Color Pallet 7'),
		('pallet_8', 'Color Pallet 8'),
		('pallet_9', 'Color Pallet 9'),
		('pallet_10', 'Color Pallet 10'),
		('pallet_11', 'Color Pallet 11'),
		('pallet_12', 'Color Pallet 12'),
		('pallet_13', 'Color Pallet 13'),
		('pallet_14', 'Color Pallet 14'),
		('pallet_15', 'Color Pallet 15'),
		('pallet_16', 'Color Pallet 16'),
		('pallet_17', 'Color Pallet 17'),
		('pallet_18', 'Color Pallet 18'),
		('pallet_19', 'Color Pallet 19 (GT)'),
	],default="pallet_19", string="Color Pallets")

	drawer_color_pallet = fields.Selection([
        ('drawer_pallet_1', 'Color Pallet 1'),
        ('drawer_pallet_2', 'Color Pallet 2'),
        ('drawer_pallet_3', 'Color Pallet 3'),
        ('drawer_pallet_4', 'Color Pallet 4'),
        ('drawer_pallet_5', 'Color Pallet 5'),
        ('drawer_pallet_6', 'Color Pallet 6'),
        ('drawer_pallet_7', 'Color Pallet 7'),
        ('drawer_pallet_8', 'Color Pallet 8'),
        ('drawer_pallet_9', 'Color Pallet 9'),
        ('drawer_pallet_10', 'Color Pallet 10'),
        ('drawer_pallet_11', 'Color Pallet 11'),
        ('drawer_pallet_12', 'Color Pallet 12'),
        ('drawer_pallet_13', 'Color Pallet 13'),
        ('drawer_pallet_14', 'Color Pallet 14'),
        ('drawer_pallet_15', 'Color Pallet 15'),
        ('drawer_pallet_16', 'Color Pallet 16'),
        ('drawer_pallet_17', 'Color Pallet 17'),
        ('drawer_pallet_18', 'Color Pallet 18'),
        ('drawer_pallet_19', 'Color Pallet 19 (GT)'),
    ], default="drawer_pallet_19", string="Drawer Color Pallets")

	appdrawer_custom_bg_color = fields.Char(string="App Drawer Custom Background Color",default="#583885")
	appdrawer_custom_text_color = fields.Char(string="App Drawer Custom Text Color",default="#ffffff")
	
	header_vertical_mini_text_color = fields.Char(string="App Header Custom Text Color",default="#2d678b")
	header_vertical_mini_bg_color = fields.Char(string="App Header Custom BG Color",default="#f9fdff")

	menu_shape_bg_color = fields.Char(string="Enterprise Menu BG Color",default="#000000")
	menu_shape_bg_color_opacity = fields.Float(string="Menu Shape BG Color Opacity",default="1")

	light_primary_bg_color = fields.Char(string="Primary Background Color for light",default="#583885")
	light_primary_text_color = fields.Char(string="Primary Text Color for light",default="#ffffff")

	apply_light_bg_img = fields.Boolean(string="Apply light bg image")
	light_bg_image = fields.Binary(string="Background Image For light", default=_default_app_drawer_bg_image, readonly=False)

	# Compatibility: some custom views (in DB) expect this field.
	# IMPORTANT: keep it non-stored so it won't require a DB column (prevents UndefinedColumn on existing DBs).
	show_filter_row = fields.Boolean(
		string="Show Filter Row",
		compute="_compute_show_filter_row",
		inverse="_inverse_show_filter_row",
		store=False,
		readonly=False,
	)

	def _compute_show_filter_row(self):
		param = self.env["ir.config_parameter"].sudo()
		val = param.get_param("spiffy_theme_backend.show_filter_row", default="0") or "0"
		val = str(val).strip().lower()
		flag = val in ("1", "true", "yes", "y", "on")
		for rec in self:
			rec.show_filter_row = flag

	def _inverse_show_filter_row(self):
		param = self.env["ir.config_parameter"].sudo()
		for rec in self:
			param.set_param("spiffy_theme_backend.show_filter_row", "1" if rec.show_filter_row else "0")

	vertical_mini_bg_image_one = fields.Binary(string="Background Image One", default=_default_vertical_mini_bg_image_one, readonly=False)
	vertical_mini_bg_image_two = fields.Binary(string="Background Image Two", default=_default_vertical_mini_bg_image_two, readonly=False)
	vertical_mini_bg_image_three = fields.Binary(string="Background Image Three", default=_default_vertical_mini_bg_image_three, readonly=False)
	vertical_mini_bg_image_four = fields.Binary(string="Background Image Four", default=_default_vertical_mini_bg_image_four, readonly=False)

	menu_bg_image = fields.Binary(string="Background Image For menu", default=_default_menu_bg_image, readonly=False)
	
	dark_primary_bg_color = fields.Char(string="Primary Background Color for dark",default="#583885")
	dark_primary_text_color = fields.Char(string="Primary Text Color for dark",default="#ffffff")

	dark_secondry_bg_color = fields.Char(string="Secondry Background Color for dark",default="#242424")
	dark_secondry_text_color = fields.Char(string="Secondry Text Color for dark",default="#ffffff")

	dark_body_bg_color = fields.Char(string="Body Background Color for dark",default="#1d1d1d")
	dark_body_text_color = fields.Char(string="Body Text Color for dark",default="#ffffff")

	separator = fields.Selection([
		('separator_style_1', 'Separator Style 1'),
		('separator_style_2', 'Separator Style 2'),
		('separator_style_3', 'Separator Style 3'),
		('separator_style_4', 'Separator Style 4')],
		default="separator_style_2", string="Separator Styles")

	tab = fields.Selection([
		('tab_style_1', 'Tab Style 1'),
		('tab_style_2', 'Tab Style 2'),
		('tab_style_3', 'Tab Style 3'),
		('tab_style_4', 'Tab Style 4')],
		default="tab_style_1", string="Tab Styles")

	checkbox = fields.Selection([
		('checkbox_style_1', 'Checkbox Style 1'),
		('checkbox_style_2', 'Checkbox Style 2'),
		('checkbox_style_3', 'Checkbox Style 3'),
		('checkbox_style_4', 'Checkbox Style 4')],
		default="checkbox_style_4", string="Checkbox Styles")

	radio = fields.Selection([
		('radio_style_1', 'Radio Style 1'),
		('radio_style_2', 'Radio Style 2'),
		('radio_style_3', 'Radio Style 3'),
		('radio_style_4', 'Radio Style 4')],
		default="radio_style_1", string="Radio Styles")

	popup = fields.Selection([
		('popup_style_1', 'popup Style 1'),
		('popup_style_2', 'popup Style 2'),
		('popup_style_3', 'popup Style 3'),
		('popup_style_4', 'popup Style 4')],
		default="popup_style_2", string="popup Styles")
	
	chatter_position = fields.Selection([
		('chatter_right', 'Chatter Right'),
		('chatter_bottom', 'Chatter Bottom')],
		default="chatter_right", string="Chatter Position")
	
	top_menu_position = fields.Selection([
		('top_menu_horizontal', 'Top Menu Horizontal'),
		('top_menu_vertical', 'Top Menu Vertical'),
		('top_menu_vertical_mini', 'Top Menu Vertical Mini'),
		('top_menu_vertical_mini_2', 'Top Menu Vertical Mini 2')],
		default="top_menu_vertical", string="Top Menu Position")

	top_menu_bg_vertical_mini_2 = fields.Selection([
		('top_menu_vertical_bg1', 'Top Menu Vertical BG 1'),
		('top_menu_vertical_bg2', 'Top Menu Vertical BG 2'),
		('top_menu_vertical_bg3', 'Top Menu Vertical BG 3'),
		('top_menu_vertical_bg4', 'Top Menu Vertical BG 4')
	], default='top_menu_vertical_bg1', string="Top Menu Vertical Backgoround Image")

	# Backward-compat alias: some databases/views refer to this older field name.
	top_menu_custom_bg_vertical_mini_2 = fields.Selection(
		selection=[
			('top_menu_vertical_bg1', 'Top Menu Vertical BG 1'),
			('top_menu_vertical_bg2', 'Top Menu Vertical BG 2'),
			('top_menu_vertical_bg3', 'Top Menu Vertical BG 3'),
			('top_menu_vertical_bg4', 'Top Menu Vertical BG 4'),
		],
		string="Top Menu Vertical Background Image (legacy)",
		compute="_compute_top_menu_custom_bg_vertical_mini_2",
		inverse="_inverse_top_menu_custom_bg_vertical_mini_2",
		store=False,
		readonly=False,
	)

	@api.depends("top_menu_bg_vertical_mini_2")
	def _compute_top_menu_custom_bg_vertical_mini_2(self):
		for rec in self:
			rec.top_menu_custom_bg_vertical_mini_2 = rec.top_menu_bg_vertical_mini_2

	def _inverse_top_menu_custom_bg_vertical_mini_2(self):
		for rec in self:
			if rec.top_menu_custom_bg_vertical_mini_2:
				rec.top_menu_bg_vertical_mini_2 = rec.top_menu_custom_bg_vertical_mini_2

	theme_style = fields.Selection([
		('biz_theme_rounded', 'Rounded Theme'),
		('biz_theme_standard', 'Standard Theme'),
		('biz_theme_square', 'Square Theme')],
		default="biz_theme_rounded", string="Theme Style")
	
	apply_menu_shape_style = fields.Boolean(string="Apply Menu Shape Stype")
	shape_style = fields.Selection([
		('biz_shape_rounded', 'Rounded Shape'),
		('biz_shape_circle', 'Circle Shape'),
		('biz_shape_square', 'Square Shape')],
		default="biz_shape_rounded", string="Shape Style")
	
	attachment_in_tree_view = fields.Boolean(string="Show Attachement in tree view")

	font_size = fields.Selection([
		('font_small', 'Font Small'),
		('font_medium', 'Font Medium'),
		('font_large', 'Font large')],
		default="font_medium", string="Font size")

	loader_style = fields.Selection([
		('loader_style_1', 'Loader Style 1'),
		('loader_style_2', 'Loader Style 2'),
		('loader_style_3', 'Loader Style 3'),
		('loader_style_4', 'Loader Style 4'),
		('loader_style_5', 'Loader Style 5'),
		('loader_style_6', 'Loader Style 6'),
		('loader_style_7', 'Loader Style 7'),
		('loader_style_8', 'Loader Style 8'),
		('loader_style_9', 'Loader Style 9'),
		('loader_style_10', 'Loader Style 10'),],
		default="loader_style_10", string="Loader Styles")
	
	font_family = fields.Selection([
		('lato', 'Lato'),
		('montserrat', 'Montserrat'),
		('open_sans', 'Open Sans'),
		('oswald', 'Oswald'),
		('raleway', 'Raleway'),
		('roboto', 'Roboto'),
		('poppins', 'Poppins'),
		('rubik', 'Rubik'),
		('inter', 'Inter'),
		('josefin_sans', 'Josefin Sans'),
		('varela_round', 'Varela Round'),
		('manrope', 'Manrope'),
		('Nunito_Sans', 'Nunito Sans'),
		('tajawal', 'Tajawal'),
		('almarai', 'Almarai'),
		('cairo', 'Cairo')],
		default="rubik", string="Font Family")

	list_view_density = fields.Selection([
		('list_comfortable', 'Comfortable'),
		('list_compact', 'Compact'),],
		default="list_comfortable", string="List View Density")
	
	input_style = fields.Selection([
		('input_borderless', 'Borderless'),
		('input_bottom_border', 'Bottom Border'),
		('input_bordered', 'Bordered'),
		], default="input_bottom_border", string="Form View Mode")

	list_view_sticky_header = fields.Boolean(string="List view Sticky Header")
