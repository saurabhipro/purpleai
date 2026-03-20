from odoo import models, fields, api

class JigsawPuzzle(models.Model):
    _name = 'jigsaw.puzzle'
    _description = 'Jigsaw Puzzle'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True, tracking=True)
    description = fields.Text(string='Description')
    difficulty = fields.Selection([
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard')
    ], string='Difficulty', default='medium', tracking=True)
    piece_count = fields.Integer(string='Piece Count')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')
    ], string='Status', default='draft', tracking=True)

    def action_start(self):
        self.state = 'in_progress'

    def action_complete(self):
        self.state = 'completed'
