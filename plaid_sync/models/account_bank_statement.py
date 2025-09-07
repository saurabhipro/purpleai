from odoo import fields, models, _, api
from odoo.exceptions import UserError


class AccountBankStatement(models.Model):
    _name = 'account.bank.statement'
    _inherit = ['account.bank.statement', 'mail.thread', 'mail.activity.mixin']

    state = fields.Selection([('open', 'new'), ('posted', 'Processing'), ('confirm', 'Validated')],
                             string='State',
                             default='open')
    all_lines_reconciled = fields.Boolean(compute='_compute_all_lines_reconciled',
                                          help="Technical field indicating if all statement lines are fully reconciled.")
    move_line_count = fields.Integer(compute="_get_move_line_count")
    country_code = fields.Char(related='company_id.account_fiscal_country_id.code')
    move_line_ids = fields.One2many('account.move.line', 'statement_id', string='Entry lines',
                                    state={'confirm': [('readonly', True)]})
    previous_statement_id = fields.Many2one('account.bank.statement',
                                            help='technical field to compute starting balance correctly',
                                            compute='_get_previous_statement', store=True)
    is_valid_balance_start = fields.Boolean(string="Is Valid Balance Start", store=True,
                                            compute="_compute_is_valid_balance_start",
                                            help="Technical field to display a warning message in case starting balance is different than previous ending balance")
    journal_type = fields.Selection(related='journal_id.type', help="Technical field used for usability purposes")
    cashbox_start_id = fields.Many2one('account.bank.statement.cashbox', string="Starting Cashbox")
    cashbox_end_id = fields.Many2one('account.bank.statement.cashbox', string="Ending Cashbox")

    @api.depends('line_ids.journal_id')
    def _compute_journal_id(self):
        for statement in self:
            if statement.line_ids:
                if len(statement.line_ids.journal_id) > 1:
                    statement.journal_id = statement.line_ids.journal_id[0]
                else:
                    statement.journal_id = statement.line_ids.journal_id
                statement.line_ids.move_id.company_id = self.env.company
                for move in statement.move_line_ids:
                    if not move.company_id:
                        move.company_id = self.env.company

    @api.depends('line_ids.internal_index', 'line_ids.state')
    def _compute_date_index(self):
        for stmt in self:
            if not stmt.date:
                stmt.date = fields.date.today()
            for rec in stmt.line_ids:
                if not rec.internal_index:
                    return
            sorted_lines = stmt.line_ids.sorted('internal_index')
            stmt.first_line_index = sorted_lines[:1].internal_index
            # stmt.date = sorted_lines.filtered(lambda l: l.state == 'posted')[-1:].date

    def button_post(self):
        ''' Move the bank statements from 'draft' to 'posted'. '''
        if any(statement.state != 'open' for statement in self):
            raise UserError(_("Only new statements can be posted."))

        self._check_cash_balance_end_real_same_as_computed()

        for statement in self:
            if not statement.name:
                statement._set_next_sequence()

        self.write({'state': 'posted'})
        lines_of_moves_to_post = self.line_ids.filtered(lambda line: line.move_id.state != 'posted')
        if lines_of_moves_to_post:
            lines_of_moves_to_post.move_id._post(soft=False)

    def _check_cash_balance_end_real_same_as_computed(self):
        """ Check the balance_end_real (encoded manually by the user) is equals to the balance_end (computed by odoo).
            For a cash statement, if there is a difference, the different is set automatically to a profit/loss account.
        """
        for statement in self.filtered(lambda stmt: stmt.journal_type == 'cash'):
            if not statement.currency_id.is_zero(statement.difference):
                st_line_vals = {
                    'statement_id': statement.id,
                    'journal_id': statement.journal_id.id,
                    'amount': statement.difference,
                    'date': statement.date,
                }

                if statement.currency_id.compare_amounts(statement.difference, 0.0) < 0.0:
                    if not statement.journal_id.loss_account_id:
                        raise UserError(_(
                            "Please go on the %s journal and define a Loss Account. "
                            "This account will be used to record cash difference.",
                            statement.journal_id.name
                        ))

                    st_line_vals['payment_ref'] = _("Cash difference observed during the counting (Loss)")
                    st_line_vals['counterpart_account_id'] = statement.journal_id.loss_account_id.id
                else:
                    # statement.difference > 0.0
                    if not statement.journal_id.profit_account_id:
                        raise UserError(_(
                            "Please go on the %s journal and define a Profit Account. "
                            "This account will be used to record cash difference.",
                            statement.journal_id.name
                        ))

                    st_line_vals['payment_ref'] = _("Cash difference observed during the counting (Profit)")
                    st_line_vals['counterpart_account_id'] = statement.journal_id.profit_account_id.id

                self.env['account.bank.statement.line'].create(st_line_vals)
        return True

    def button_validate(self):
        if any(statement.state != 'posted' or not statement.all_lines_reconciled for statement in self):
            raise UserError(_('All the account entries lines must be processed in order to validate the statement.'))

        for statement in self:

            # Chatter.
            statement.message_post(body=_('Statement %s confirmed.', statement.name))

            # Bank statement report.
            if statement.journal_id.type == 'bank':
                content, content_type = self.env.ref('account.action_report_account_statement')._render(statement.id)
                self.env['ir.attachment'].create({
                    'name': statement.name and _("Bank Statement %s.pdf", statement.name) or _("Bank Statement.pdf"),
                    'type': 'binary',
                    'raw': content,
                    'res_model': statement._name,
                    'res_id': statement.id
                })

        self._check_balance_end_real_same_as_computed()
        self.write({'state': 'confirm', 'date_done': fields.Datetime.now()})

    def button_reopen(self):
        ''' Move the bank statements back to the 'open' state. '''
        if any(statement.state == 'draft' for statement in self):
            raise UserError(_("Only validated statements can be reset to new."))

        self.write({'state': 'open'})
        self.line_ids.move_id.button_draft()
        self.line_ids.button_undo_reconciliation()

    def button_reprocess(self):
        """Move the bank statements back to the 'posted' state."""
        if any(statement.state != 'confirm' for statement in self):
            raise UserError(_("Only Validated statements can be reset to new."))

        self.write({'state': 'posted', 'date_done': False})

    def button_validate_or_action(self):
        if self.journal_type == 'cash' and not self.currency_id.is_zero(self.difference):
            return self.env['ir.actions.act_window']._for_xml_id('account.action_view_account_bnk_stmt_check')

        return self.button_validate()

    def button_journal_entries(self):
        return {
            'name': _('Journal Entries'),
            'view_mode': 'tree',
            'res_model': 'account.move.line',
            'view_id': self.env.ref('account.view_move_line_tree_grouped_bank_cash').id,
            'type': 'ir.actions.act_window',
            'domain': [('move_id', 'in', self.line_ids.move_id.ids)],
            'context': {
                'journal_id': self.journal_id.id,
                'group_by': 'move_id',
                'expand': True
            }
        }

    def open_cashbox_id(self):
        self.ensure_one()
        context = dict(self.env.context or {})
        if context.get('balance'):
            context['statement_id'] = self.id
            if context['balance'] == 'start':
                cashbox_id = self.cashbox_start_id.id
            elif context['balance'] == 'close':
                cashbox_id = self.cashbox_end_id.id
            else:
                cashbox_id = False

            action = {
                'name': _('Cash Control'),
                'view_mode': 'form',
                'res_model': 'account.bank.statement.cashbox',
                'view_id': self.env.ref('account.view_account_bnk_stmt_cashbox_footer').id,
                'type': 'ir.actions.act_window',
                'res_id': cashbox_id,
                'context': context,
                'target': 'new'
            }

            return action

    @api.depends('balance_start', 'previous_statement_id')
    def _compute_is_valid_balance_start(self):
        for bnk in self:
            bnk.is_valid_balance_start = (
                bnk.currency_id.is_zero(
                    bnk.balance_start - bnk.previous_statement_id.balance_end_real
                )
                if bnk.previous_statement_id
                else True
            )

    @api.depends('date', 'journal_id')
    def _get_previous_statement(self):
        for st in self:
            # Search for the previous statement
            domain = [('date', '<=', st.date), ('journal_id', '=', st.journal_id.id)]
            # The reason why we have to perform this test is because we have two use case here:
            # First one is in case we are creating a new record, in that case that new record does
            # not have any id yet. However, if we are updating an existing record, the domain date <= st.date
            # will find the record itself, so we have to add a condition in the search to ignore self.id
            if not isinstance(st.id, models.NewId):
                domain.extend(['|', '&', ('id', '<', st.id), ('date', '=', st.date), '&', ('id', '!=', st.id),
                               ('date', '!=', st.date)])
            previous_statement = self.search(domain, limit=1, order='date desc, id desc')
            st.previous_statement_id = previous_statement.id

    def write(self, values):
        res = super(AccountBankStatement, self).write(values)
        if values.get('date') or values.get('journal'):
            # If we are changing the date or journal of a bank statement, we have to change its previous_statement_id. This is done
            # automatically using the compute function, but we also have to change the previous_statement_id of records that were
            # previously pointing toward us and records that were pointing towards our new previous_statement_id. This is done here
            # by marking those record as needing to be recomputed.
            # Note that marking the field is not enough as we also have to recompute all its other fields that are depending on 'previous_statement_id'
            # hence the need to call modified afterward.
            to_recompute = self.search([('previous_statement_id', 'in', self.ids), ('id', 'not in', self.ids),
                                        ('journal_id', 'in', self.mapped('journal_id').ids)])
            if to_recompute:
                self.env.add_to_compute(self._fields['previous_statement_id'], to_recompute)
                to_recompute.modified(['previous_statement_id'])
            next_statements_to_recompute = self.search(
                [('previous_statement_id', 'in', [st.previous_statement_id.id for st in self]),
                 ('id', 'not in', self.ids), ('journal_id', 'in', self.mapped('journal_id').ids)])
            if next_statements_to_recompute:
                self.env.add_to_compute(self._fields['previous_statement_id'], next_statements_to_recompute)
                next_statements_to_recompute.modified(['previous_statement_id'])
        return res

    @api.model_create_multi
    def create(self, values):
        res = super(AccountBankStatement, self).create(values)
        # Upon bank stmt creation, it is possible that the statement is inserted between two other statements and not at the end
        # In that case, we have to search for statement that are pointing to the same previous_statement_id as ourselve in order to
        # change their previous_statement_id to us. This is done by marking the field 'previous_statement_id' to be recomputed for such records.
        # Note that marking the field is not enough as we also have to recompute all its other fields that are depending on 'previous_statement_id'
        # hence the need to call modified afterward.
        # The reason we are doing this here and not in a compute field is that it is not easy to write dependencies for such field.
        next_statements_to_recompute = self.search(
            [('previous_statement_id', 'in', [st.previous_statement_id.id for st in res]), ('id', 'not in', res.ids),
             ('journal_id', 'in', res.journal_id.ids)])
        if next_statements_to_recompute:
            self.env.add_to_compute(self._fields['previous_statement_id'], next_statements_to_recompute)
            next_statements_to_recompute.modified(['previous_statement_id'])
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_only_if_open(self):
        for statement in self:
            if statement.state != 'open':
                raise UserError(
                    _('In order to delete a bank statement, you must first cancel it to delete related journal items.'))

    def unlink(self):
        for statement in self:
            # Explicitly unlink bank statement lines so it will check that the related journal entries have been deleted first
            statement.line_ids.unlink()
            # Some other bank statements might be link to this one, so in that case we have to switch the previous_statement_id
            # from that statement to the one linked to this statement
            next_statement = self.search(
                [('previous_statement_id', '=', statement.id), ('journal_id', '=', statement.journal_id.id)])
            if next_statement:
                next_statement.previous_statement_id = statement.previous_statement_id
        return super(AccountBankStatement, self).unlink()

    @api.depends('move_line_ids')
    def _get_move_line_count(self):
        for statement in self:
            statement.move_line_count = len(statement.move_line_ids)

    @api.depends('line_ids.is_reconciled')
    def _compute_all_lines_reconciled(self):
        for statement in self:
            statement.all_lines_reconciled = all(st_line.is_reconciled for st_line in statement.line_ids)

    @api.depends('create_date')
    def _compute_balance_start(self):
        for stmt in self.sorted(lambda x: x.first_line_index or '0'):
            journal_id = stmt.journal_id.id or stmt.line_ids.journal_id.id
            previous_line_with_statement = self.env['account.bank.statement.line'].search([
                ('internal_index', '<', stmt.first_line_index),
                ('journal_id', '=', journal_id),
                ('state', '=', 'posted'),
                ('statement_id', '!=', False),
            ], limit=1)
            balance_start = previous_line_with_statement.statement_id.balance_end_real

            lines_in_between_domain = [
                ('internal_index', '<', stmt.first_line_index),
                ('journal_id', '=', journal_id),
                ('state', '=', 'posted'),
            ]
            if previous_line_with_statement:
                lines_in_between_domain.append(('internal_index', '>', previous_line_with_statement.internal_index))
                # remove lines from previous statement (when multi-editing a line already in another statement)
                previous_st_lines = previous_line_with_statement.statement_id.line_ids
                lines_in_common = previous_st_lines.filtered(lambda l: l.id in stmt.line_ids._origin.ids)
                balance_start -= sum(lines_in_common.mapped('amount'))

            lines_in_between = self.env['account.bank.statement.line'].search(lines_in_between_domain)
            balance_start += sum(lines_in_between.mapped('amount'))

            stmt.balance_start = balance_start

    @api.depends('balance_start', 'line_ids.amount', 'line_ids.state')
    def _compute_balance_end(self):
        for stmt in self:
            lines = stmt.line_ids.filtered(lambda x: x.state == 'posted')
            stmt.balance_end_real = stmt.balance_end = stmt.balance_start + sum(lines.mapped('amount'))

    @api.depends('balance_start')
    def _compute_balance_end_real(self):
        for stmt in self:
            stmt.balance_end_real = stmt.balance_end

    """
        Returns the wizard to get transactions from Plaid for a connected journal
    """

    def get_transactions(self):
        return {
            'name': 'Get Transactions',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'plaid.transaction.wizard',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {'default_journal_id': self.journal_id.id}
        }


class AccountBankStmtCashWizard(models.Model):
    """
    Account Bank Statement popup that allows entering cash details.
    """
    _name = 'account.bank.statement.cashbox'
    _description = 'Bank Statement Cashbox'
    _rec_name = 'id'

    cashbox_lines_ids = fields.One2many('account.cashbox.line', 'cashbox_id', string='Cashbox Lines')
    start_bank_stmt_ids = fields.One2many('account.bank.statement', 'cashbox_start_id')
    end_bank_stmt_ids = fields.One2many('account.bank.statement', 'cashbox_end_id')
    total = fields.Float(compute='_compute_total')
    currency_id = fields.Many2one('res.currency', compute='_compute_currency')

    @api.depends('start_bank_stmt_ids', 'end_bank_stmt_ids')
    def _compute_currency(self):
        for cashbox in self:
            cashbox.currency_id = False
            if cashbox.end_bank_stmt_ids:
                cashbox.currency_id = cashbox.end_bank_stmt_ids[0].currency_id
            if cashbox.start_bank_stmt_ids:
                cashbox.currency_id = cashbox.start_bank_stmt_ids[0].currency_id

    @api.depends('cashbox_lines_ids', 'cashbox_lines_ids.coin_value', 'cashbox_lines_ids.number')
    def _compute_total(self):
        for cashbox in self:
            cashbox.total = sum([line.subtotal for line in cashbox.cashbox_lines_ids])

    @api.model
    def default_get(self, fields):
        vals = super(AccountBankStmtCashWizard, self).default_get(fields)
        balance = self.env.context.get('balance')
        statement_id = self.env.context.get('statement_id')
        if 'start_bank_stmt_ids' in fields and not vals.get(
                'start_bank_stmt_ids') and statement_id and balance == 'start':
            vals['start_bank_stmt_ids'] = [(6, 0, [statement_id])]
        if 'end_bank_stmt_ids' in fields and not vals.get('end_bank_stmt_ids') and statement_id and balance == 'close':
            vals['end_bank_stmt_ids'] = [(6, 0, [statement_id])]

        return vals

    def name_get(self):
        result = []
        for cashbox in self:
            result.append((cashbox.id, str(cashbox.total)))
        return result

    @api.model_create_multi
    def create(self, vals):
        cashboxes = super(AccountBankStmtCashWizard, self).create(vals)
        cashboxes._validate_cashbox()
        return cashboxes

    def write(self, vals):
        res = super(AccountBankStmtCashWizard, self).write(vals)
        self._validate_cashbox()
        return res

    def _validate_cashbox(self):
        for cashbox in self:
            if cashbox.start_bank_stmt_ids:
                cashbox.start_bank_stmt_ids.write({'balance_start': cashbox.total})
            if cashbox.end_bank_stmt_ids:
                cashbox.end_bank_stmt_ids.write({'balance_end_real': cashbox.total})


class AccountCashboxLine(models.Model):
    """ Cash Box Details """
    _name = 'account.cashbox.line'
    _description = 'CashBox Line'
    _rec_name = 'coin_value'
    _order = 'coin_value'

    @api.depends('coin_value', 'number')
    def _sub_total(self):
        """ Calculates Sub total"""
        for cashbox_line in self:
            cashbox_line.subtotal = cashbox_line.coin_value * cashbox_line.number

    coin_value = fields.Float(string='Coin/Bill Value', required=True, digits=0)
    number = fields.Integer(string='#Coins/Bills', help='Opening Unit Numbers')
    subtotal = fields.Float(compute='_sub_total', string='Subtotal', digits=0, readonly=True)
    cashbox_id = fields.Many2one('account.bank.statement.cashbox', string="Cashbox")
    currency_id = fields.Many2one('res.currency', related='cashbox_id.currency_id')
