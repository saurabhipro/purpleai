from odoo import models, fields, api

class AuditFormDefinition(models.Model):
    _name = 'audit.form.definition'
    _description = 'Audit Memo Dynamic Field Definition'
    _order = 'sequence, id'

    name = fields.Char(string="Field Label", required=True, translate=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(default=True)
    field_type = fields.Selection([
        ('char', 'Single Line Text'),
        ('text', 'Multi-line Text')
    ], string="Field Type", default='text', required=True)
    help_text = fields.Char(string="Help / Placeholder")

    @api.model
    def create(self, vals):
        definition = super(AuditFormDefinition, self).create(vals)
        # Auto-create this field for all OPEN memos to save user clicks?
        # User said: "coming in all ememmo forms ad nwe dont have to add in every for m seperatlt"
        # This implies immediate availability.
        
        # Performance warning: If 1000s of memos, this is slow. 
        # But this is an 'Audit Tool', likely manageable volume.
        
        # Find all memos that are not done/rejected? Or ALL? 
        # Typically you want it on active ones. Let's do ALL to be safe.
        memos = self.env['audit.memo'].search([])
        CustomField = self.env['audit.memo.custom.field']
        
        new_lines = []
        for memo in memos:
            # Double check if it exists (unlikely since we just created the definition)
            # But standard checks are good.
            new_lines.append({
                'memo_id': memo.id,
                'definition_id': definition.id,
            })
        
        if new_lines:
            CustomField.create(new_lines)
            
        return definition

class AuditMemoCustomField(models.Model):
    _name = 'audit.memo.custom.field'
    _description = 'Audit Memo Custom Field Value'
    _order = 'sequence, id'

    memo_id = fields.Many2one('audit.memo', string="Memo", ondelete='cascade')
    definition_id = fields.Many2one('audit.form.definition', string="Field Definition", required=True, ondelete='restrict')
    
    # Related fields for UI display
    name = fields.Char(related='definition_id.name', string="Label", readonly=True)
    sequence = fields.Integer(related='definition_id.sequence', string="Sequence", readonly=True, store=True)
    field_type = fields.Selection(related='definition_id.field_type', readonly=True)
    
    # Value storage
    value_char = fields.Char(string="Value")
    value_text = fields.Text(string="Value (Text)")

    # Unified computation or UI logic could be used, but for simplicity we might show two fields 
    # and use invisible attribute, OR just use one Text field for everything if the user asked for "Text fields".
    # User asked: "add new fields in memo form text fields".
    # Let's simplify and just use one Text field `value` for everything to keep UI clean.
    # The 'field_type' in definition can control the widget (input vs textarea) if we want, 
    # but dynamic widget in list view is hard.
    # We will use a standard Text field.
    
    value = fields.Text(string="Answer")
