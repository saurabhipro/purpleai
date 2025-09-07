from odoo import models, fields, _, api
import plaid
import json
from plaid.api import plaid_api
from odoo.exceptions import UserError, ValidationError
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.link_token_account_filters import LinkTokenAccountFilters
from plaid.model.depository_account_subtypes import DepositoryAccountSubtypes
from plaid.model.depository_account_subtype import DepositoryAccountSubtype
from plaid.model.depository_filter import DepositoryFilter
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.products import Products
from plaid.model.country_code import CountryCode
from urllib3.exceptions import MaxRetryError


class OnlineSyncPlaid(models.Model):
    _name = 'online.sync.plaid'
    _description = 'Online Plaid Synchronization'
    _rec_name = 'plaid_institution_name'

    bank_journal_id = fields.Many2one('account.journal', string="Bank Name", domain=[('type', '=', 'bank')],
                                      help='Select bank journal which you want to sync to Plaid')
    state = fields.Selection([('unlinked', 'Not Connected'), ('linked', 'Connected')], default='unlinked')

    plaid_access_token = fields.Char(invisible=True)
    plaid_item_id = fields.Char(invisible=True)
    plaid_institution_id = fields.Char(invisible=True)
    plaid_institution_name = fields.Char(string='Institution Name', help='Respective institution name on Plaid')

    accounts_line_ids = fields.One2many('online.sync.plaid.lines', 'plaid_sync_id', string="Accounts")


    def get_environment(self):
        plaid_env = self.env['ir.config_parameter'].get_param('plaid_sync.plaid_account_setting')

        if plaid_env:
            return plaid_env
        else:
            return 'production'

    def name_get(self):
        rec_names = []
        for rec in self:
            rec_names.append((rec.id, rec.bank_journal_id.name + " - " + str(rec.plaid_institution_name or "")))
        return rec_names

    def get_plaid_client(self, client_id, secret):
        environment = self.get_environment()
        if environment == 'sandbox':
            host = plaid.Environment.Sandbox
        elif environment == 'development':
            host = plaid.Environment.Development
        elif environment == 'production':
            host = plaid.Environment.Production
        else:
            host = plaid.Environment.Production

        configuration = plaid.Configuration(
            host=host,
            api_key={
                'clientId': client_id,
                'secret': secret,
            }
        )
        api_client = plaid.ApiClient(configuration)
        return plaid_api.PlaidApi(api_client)

    """
        The function is used to create credentials for Plaid API
        - Create configuration object from client_id and secret
        - Create API Client from configuration object
        - Create Plaid Client from API Client
        - Create Link Token Request
        - Get response from Plaid Client
        - Return the Link Token
    """

    @api.model
    def create_credentials(self, client_id, secret):
        global client
        client = self.get_plaid_client(client_id, secret)
        # TODO: Add more products in upcoming releases
        request = LinkTokenCreateRequest(
            # products=[Products('auth'), Products('transactions')],
            products=[Products('transactions')],
            client_name="Online Plaid Synchronization",
            # TODO: Work on adding new country codes as well as give option somewhere to select
            country_codes=[
                CountryCode('US'),
                CountryCode('CA'),
                # CountryCode('GB'),
                # CountryCode('DE'),
                # CountryCode('FR'),
                # CountryCode('NL'),
                # CountryCode('IE'),
                # CountryCode('ES')
            ],
            language='en',
            webhook='https://sample-webhook-uri.com',
            link_customization_name='default',
            account_filters=LinkTokenAccountFilters(
                depository=DepositoryFilter(
                    account_subtypes=DepositoryAccountSubtypes(
                        [DepositoryAccountSubtype('checking'), DepositoryAccountSubtype('savings')]
                    )
                )
            ),
            user=LinkTokenCreateRequestUser(
                client_user_id='axiom_world_plaid_app'
            )
        )
        try:
            response = client.link_token_create(request)
        except MaxRetryError as e:
            raise UserError(_("There was a problem while creating the token."))
        return json.dumps({'key': response['link_token']})

    """
            The function is used to start the process of syncing with Plaid
            - Returns the client action
    """

    def start_sync(self):
        ctx = self.env.context.copy()
        company = self.env.company
        if not self.env.company.plaid_client:
            raise ValidationError(_('Please set the Plaid Client ID in settings'))
        if not self.env.company.plaid_secret:
            raise ValidationError(_('Please set the Plaid Secret in settings'))
        environment = self.get_environment()
        ctx.update({'rec_id': self.id, 'plaid_client': company.plaid_client, 'plaid_secret': company.plaid_secret,
                    'environment': environment})
        return {
            "type": "ir.actions.client",
            "tag": "plaid_online_sync_widget",
            'target': 'new',
            'context': ctx,
        }

    """
            The function performs action on callback from Plaid API
            - Exchange public token
            - Get access token
            - Get institution ID
            - Get institution name
            - Get item ID
            - Get account types
    """

    def link_success(self, rec_id, public_token, metadata):
        # convert public token to access_token and create a provider with accounts defined in metadata
        global client
        exchange_request = ItemPublicTokenExchangeRequest(
            public_token=public_token
        )
        exchange_response = client.item_public_token_exchange(exchange_request)
        rec = self.browse(rec_id)
        rec.plaid_access_token = exchange_response.get('access_token', False)
        rec.plaid_institution_id = metadata.get('institution', {}).get('institution_id', '')
        rec.plaid_institution_name = metadata.get('institution', {}).get('name', '')
        rec.plaid_item_id = exchange_response.get('item_id', False)
        lines = [(0, 0, {'account_id': x['id'],
                         'account_name': x['name'],
                         'account_type': x['type'],
                         'account_type': x['subtype']}) for x in metadata.get('accounts')]
        rec.accounts_line_ids = lines
        rec.state = 'linked'

    """
            The function is used to prevent deletion of connected records
    """

    def unlink(self):
        if self.state == 'linked':
            raise ValidationError(_('Cannot delete a record that is connected to Plaid!'))
        return super(OnlineSyncPlaid, self).unlink()

    """
        The function is used to prevent creation of multiple records with the same bank journal.
    """

    @api.model
    def create(self, vals):
        rec = super(OnlineSyncPlaid, self).create(vals)
        if self.search([('bank_journal_id', '=', rec.bank_journal_id.id), ('id', '!=', rec.id)]):
            raise ValidationError(_('Cannot create more than one record for the same bank!'))
        return rec
