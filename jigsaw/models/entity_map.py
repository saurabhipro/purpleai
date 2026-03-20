from odoo import models, fields, api
import json

class JigsawEntity(models.Model):
    _name = 'jigsaw.entity'
    _description = 'Jigsaw Entity'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True, tracking=True)
    entity_id_external = fields.Char(string='Entity ID')
    type = fields.Selection([
        ('individual', 'Individual'),
        ('company', 'Company'),
        ('trust', 'Trust'),
        ('fund', 'Fund'),
        ('gov', 'Government Entity'),
        ('org_unit', 'Organization Unit'),
        ('asset', 'Asset'),
        ('account', 'Account'),
        ('legal_case', 'Legal Case'),
        ('event', 'Event')
    ], string='Type', default='company', required=True)
    
    subtype = fields.Selection([
        ('listed', 'Listed Company'),
        ('private', 'Private Company'),
        ('llc', 'LLC'),
        ('partnership', 'Partnership'),
        ('spv', 'Special Purpose Vehicle')
    ], string='Subtype')

    jurisdiction = fields.Char(string='Jurisdiction', help="e.g. Delaware, British Columbia")
    registration_no = fields.Char(string='Registration No')
    partner_id = fields.Many2one('res.partner', string='Related Partner')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    metadata_json = fields.Text(string='Metadata (JSON)')
    
    country_id = fields.Many2one('res.country', string='Country')
    avatar = fields.Binary(string='Avatar/Logo')
    
    # New Properties from UI
    commitment_amount = fields.Float(string='Commitment Amount')
    capital_contributed = fields.Float(string='Capital Contributed')
    tax_id_number = fields.Char(string='Tax ID Number')
    registered_office = fields.Text(string='Registered Office')
    formation_date = fields.Date(string='Formation / Incorporation Date')
    fund_family_name = fields.Char(string='Fund Family')
    directors = fields.Char(string='Directors')
    officers = fields.Char(string='Officers')
    authorised_signatory = fields.Char(string='Authorised Signatory')
    region = fields.Char(string='Region')
    tax_filing_deadline = fields.Date(string='Tax Filing Deadline')
    
    diagram_id = fields.Many2one('jigsaw.diagram', string='Diagram')
    
    relation_ids = fields.One2many('jigsaw.relation', 'source_entity_id', string='Outgoing Relationships')
    target_relation_ids = fields.One2many('jigsaw.relation', 'target_entity_id', string='Incoming Relationships')
    
    event_ids = fields.One2many('jigsaw.event', 'entity_id', string='Events')
    transaction_ids = fields.Many2many('jigsaw.transaction', string='Transactions')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.diagram_id:
                record.diagram_id.entity_ids = [(4, record.id)]
        return records

class JigsawRelation(models.Model):
    _name = 'jigsaw.relation'
    _description = 'Jigsaw Relation'

    source_entity_id = fields.Many2one('jigsaw.entity', string='Source Entity', required=True, ondelete='cascade')
    target_entity_id = fields.Many2one('jigsaw.entity', string='Target Entity', required=True, ondelete='cascade')
    
    ownership_pct = fields.Float(string='Ownership %', default=0.0)
    control_pct = fields.Float(string='Control %', default=0.0)
    
    relationship_type = fields.Selection([
        ('owns', 'OWNS'),
        ('controls', 'CONTROLS'),
        ('director', 'DIRECTOR_OF'),
        ('beneficiary', 'BENEFICIARY_OF'),
        ('trustee', 'TRUSTEE_OF'),
        ('reports', 'REPORTS_TO'),
        ('transferred', 'TRANSFERRED_TO'),
        ('guarantees', 'GUARANTEES'),
        ('partner', 'PARTNER_IN'),
        ('litigates', 'LITIGATES_AGAINST')
    ], string='Relation Type', default='owns')
    
    effective_from = fields.Date(string='Effective From')
    effective_to = fields.Date(string='Effective To')
    amount = fields.Monetary(string='Amount')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    description = fields.Char(string='Description')

class JigsawDiagram(models.Model):
    _name = 'jigsaw.diagram'
    _description = 'Jigsaw Structure Diagram'
    
    name = fields.Char(string='Diagram Name', required=True)
    description = fields.Text(string='Description')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    # Store layout as JSON: { "entity_id": { "x": 100, "y": 200 }, ... }
    layout_data = fields.Text(string='Layout Data', default='{}')
    
    entity_ids = fields.Many2many('jigsaw.entity', string='Entities')
    
    def action_open_workshop(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'jigsaw.workshop',
            'params': {
                'diagram_id': self.id,
            },
            'context': {
                'default_diagram_id': self.id,
                'active_id': self.id,
                'active_model': 'jigsaw.diagram',
            },
            'target': 'current',
        }
    
    @api.model
    def get_diagram_data(self, diagram_id):
        diagram = self.browse(diagram_id)
        
        # Start with entities explicitly in the diagram
        seed_entity_ids = diagram.entity_ids.ids
        if not seed_entity_ids:
            return {'nodes': [], 'links': [], 'layout': {}}

        # Recursively find all connected entities
        all_entity_ids = set(seed_entity_ids)
        to_process = set(seed_entity_ids)
        processed = set()
        
        all_relations = self.env['jigsaw.relation']
        
        while to_process:
            current_id = to_process.pop()
            processed.add(current_id)
            
            # Find relations connected to this entity
            rels = self.env['jigsaw.relation'].search([
                '|', ('source_entity_id', '=', current_id), ('target_entity_id', '=', current_id)
            ])
            all_relations |= rels
            
            for rel in rels:
                pid, cid = rel.source_entity_id.id, rel.target_entity_id.id
                if pid not in processed:
                    all_entity_ids.add(pid)
                    to_process.add(pid)
                if cid not in processed:
                    all_entity_ids.add(cid)
                    to_process.add(cid)

        entities = self.env['jigsaw.entity'].browse(list(all_entity_ids))
        
        nodes = []
        for entity in entities:
            nodes.append({
                'id': entity.id,
                'name': entity.name,
                'type': entity.type,
                'country': entity.country_id.code if entity.country_id else False,
                'jurisdiction': entity.jurisdiction or (entity.country_id.name if entity.country_id else False),
                'subtype': entity.subtype or '',
                'registration_no': entity.registration_no or '',
                'entity_id_external': entity.entity_id_external or '',
                'commitment_amount': entity.commitment_amount or 0.0,
                'capital_contributed': entity.capital_contributed or 0.0,
                'tax_id_number': entity.tax_id_number or '',
                'registered_office': entity.registered_office or '',
                'formation_date': entity.formation_date.strftime('%Y-%m-%d') if entity.formation_date else '',
                'fund_family_name': entity.fund_family_name or '',
                'directors': entity.directors or '',
                'officers': entity.officers or '',
                'authorised_signatory': entity.authorised_signatory or '',
                'region': entity.region or '',
                'tax_filing_deadline': entity.tax_filing_deadline.strftime('%Y-%m-%d') if entity.tax_filing_deadline else '',
            })
            
        links = []
        for rel in all_relations:
            links.append({
                'source': rel.source_entity_id.id,
                'target': rel.target_entity_id.id,
                'percent': rel.ownership_pct,
                'type': rel.relationship_type,
            })
            
        return {
            'nodes': nodes,
            'links': links,
            'layout': json.loads(diagram.layout_data or '{}')
        }

class JigsawEvent(models.Model):
    _name = 'jigsaw.event'
    _description = 'Entity Event'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Event Name', required=True)
    date = fields.Date(string='Date')
    entity_id = fields.Many2one('jigsaw.entity', string='Entity')
    description = fields.Text(string='Description')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

class JigsawTransaction(models.Model):
    _name = 'jigsaw.transaction'
    _description = 'Entity Transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Transaction Ref', required=True)
    date = fields.Date(string='Date')
    source_entity_id = fields.Many2one('jigsaw.entity', string='Source Entity')
    target_entity_id = fields.Many2one('jigsaw.entity', string='Target Entity')
    amount = fields.Monetary(string='Amount')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    description = fields.Text(string='Description')


