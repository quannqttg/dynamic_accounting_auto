# -*- coding: utf-8 -*-
from odoo import api, fields, models

class DynamicAccountingConfigWizard(models.TransientModel):
    _name = "dynamic.accounting.config.wizard"
    _description = "Dynamic Accounting (CE) Configuration Wizard"

    apply_fifo = fields.Boolean(default=True, string="Set FIFO + Automated valuation for all categories")
    set_expense_6320 = fields.Boolean(default=True, string="Set Expense account = 6320 on categories")
    create_1568_1569 = fields.Boolean(default=True, string="Ensure 1568/1569 exist")
    ensure_stk = fields.Boolean(default=True, string="Ensure STK Journal exists")

    def action_apply(self):
        """Minimal glue that calls helper logic in nguyenan.py if present, or performs safe defaults."""
        env = self.env
        # Try to call helpers if the script is available (optional).
        # Fall back to a minimal in-module safe setup.

        # Ensure accounts/journal
        if self.create_1568_1569:
            Acct = env['account.account'].with_context(active_test=False)
            for code, name in (('1568', '1568 Tài khoản tạm nhập (Interim Received)'),
                               ('1569', '1569 Tài khoản tạm xuất (Interim Delivered)')):
                if not Acct.search([('code','=',code)], limit=1):
                    Acct.create({'name': name, 'code': code, 'account_type': 'asset_current', 'internal_group': 'asset'})
        if self.ensure_stk:
            J = env['account.journal'].with_context(active_test=False)
            if not J.search(['|',('name','=','Định giá tồn kho'),('code','=','STK')], limit=1):
                J.create({'name':'Định giá tồn kho', 'code':'STK', 'type':'general'})

        # Apply FIFO + real_time + accounts on categories
        if self.apply_fifo:
            Acct = env['account.account'].with_context(active_test=False)
            Cat  = env['product.category'].with_context(active_test=False)
            J    = env['account.journal'].with_context(active_test=False)
            acc1561 = Acct.search([('code','=','1561')], limit=1)
            acc1568 = Acct.search([('code','=','1568')], limit=1)
            acc1569 = Acct.search([('code','=','1569')], limit=1)
            stk = J.search(['|',('name','=','Định giá tồn kho'),('code','=','STK')], limit=1)
            if acc1561 and acc1568 and acc1569 and stk:
                for c in Cat.search([]):
                    c.write({
                        'property_cost_method': 'fifo',
                        'property_valuation': 'real_time',
                        'property_stock_journal': stk.id,
                        'property_stock_valuation_account_id': acc1561.id,
                        'property_stock_account_input_categ_id': acc1568.id,
                        'property_stock_account_output_categ_id': acc1569.id,
                    })

        # Set Expense=6320 on categories with real_time
        if self.set_expense_6320:
            Acct = env['account.account'].with_context(active_test=False)
            Cat  = env['product.category'].with_context(active_test=False)
            a6320 = Acct.search([('code','=','6320')], limit=1)
            if a6320:
                for c in Cat.search([('property_valuation','=','real_time')]):
                    if c.property_account_expense_categ_id.id != a6320.id:
                        c.write({'property_account_expense_categ_id': a6320.id})

        return {'type': 'ir.actions.act_window_close'}
