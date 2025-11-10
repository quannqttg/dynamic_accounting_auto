# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class DynamicAccountingConfigWizard(models.TransientModel):
    _name = 'dynamic.accounting.config.wizard'
    _description = 'Wizard cấu hình tài khoản kế toán tự động'

    # --- Cấu hình tài khoản tồn kho ---
    valuation_code = fields.Char(string='Mã TK Định giá', default='1561', required=True)
    input_code     = fields.Char(string='Mã TK Tạm nhập', default='1568', required=True)
    output_code    = fields.Char(string='Mã TK Tạm xuất', default='1569', required=True)

    # --- Cấu hình sổ nhật ký ---
    journal_code = fields.Char(string='Mã Sổ nhật ký', default='STK', required=True)
    journal_name = fields.Char(string='Tên Sổ nhật ký', default='Định giá tồn kho', required=True)

    # --- Chi phí (COGS) ---
    expense_code = fields.Char(string='Mã TK Chi phí', default='6320', required=True)
    set_expense_account = fields.Boolean(string='Thiết lập TK Chi phí', default=True)

    # --- Áp dụng ---
    apply_to_categories = fields.Boolean(string='Áp dụng cho danh mục', default=True)

    # --- AR/AP mặc định ---
    ar_code = fields.Char(string='Mã TK Phải thu (AR)', default='1311', required=True)
    ap_code = fields.Char(string='Mã TK Phải trả (AP)', default='3311', required=True)
    set_partner_defaults = fields.Boolean(string='Đặt mặc định AR/AP cho đối tác mới', default=True)
    update_existing_partners = fields.Selection([
        ('no', 'Không cập nhật đối tác hiện có'),
        ('missing_only', 'Chỉ cập nhật khi đang để trống'),
        ('all', 'Cập nhật tất cả đối tác')
    ], string='Cập nhật đối tác hiện có', default='missing_only')

    # --- Kết quả ---
    result_message = fields.Html(string='Kết quả', readonly=True)

    # ----------------- Helpers -----------------
    def _ensure_account_exists(self, code, name, account_type='asset_current', internal_group='asset', reconcile=False):
        """Tạo tài khoản nếu chưa có - Odoo 18 không có company_id trên account"""
        Account = self.env['account.account'].sudo()
        
        # Tìm theo code (không filter company_id vì field không tồn tại)
        account = Account.search([('code', '=', str(code))], limit=1)
        
        if account:
            _logger.info("Tài khoản %s đã tồn tại: %s", code, account.name)
            return account, False
        
        try:
            # Tạo mới - KHÔNG truyền company_id
            account = Account.create({
                'name': name,
                'code': str(code),
                'account_type': account_type,
                'internal_group': internal_group,
                'reconcile': reconcile,
            })
            _logger.info("Đã tạo tài khoản %s: %s", code, name)
            return account, True
        except Exception as e:
            _logger.error("Lỗi tạo tài khoản %s: %s", code, e)
            raise UserError(_("Không thể tạo tài khoản %s: %s") % (code, e))

    def _ensure_stock_journal(self):
        """Tạo sổ nhật ký nếu chưa có"""
        Journal = self.env['account.journal'].sudo()
        
        # Journal VẪN CÓ company_id
        journal = Journal.search([
            ('code', '=', self.journal_code),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if journal:
            _logger.info("Sổ nhật ký %s đã tồn tại", self.journal_code)
            return journal, False
        
        try:
            journal = Journal.create({
                'name': self.journal_name,
                'code': self.journal_code,
                'type': 'general',
                'company_id': self.env.company.id,
            })
            _logger.info("Đã tạo sổ nhật ký %s", self.journal_code)
            return journal, True
        except Exception as e:
            _logger.error("Lỗi tạo sổ nhật ký: %s", e)
            raise UserError(_("Không thể tạo sổ nhật ký: %s") % e)

    def _apply_to_categories(self, acc_valuation, acc_input, acc_output, journal):
        """Áp dụng FIFO + Real-time cho tất cả danh mục"""
        Category = self.env['product.category'].sudo()
        categories = Category.search([])
        updated = 0
        
        for cat in categories:
            vals = {
                'property_cost_method': 'fifo',
                'property_valuation': 'real_time',
                'property_stock_journal': journal.id,
                'property_stock_valuation_account_id': acc_valuation.id,
                'property_stock_account_input_categ_id': acc_input.id,
                'property_stock_account_output_categ_id': acc_output.id,
            }
            try:
                cat.write(vals)
                updated += 1
            except Exception as e:
                _logger.warning("Không thể cập nhật danh mục %s: %s", cat.display_name, e)
        
        return updated, len(categories)

    def _set_expense_accounts(self):
        """Set expense account cho các danh mục real-time"""
        Account = self.env['account.account'].sudo()
        Category = self.env['product.category'].sudo()
        
        # Tìm expense account - KHÔNG filter company_id
        expense = Account.search([
            ('code', '=', self.expense_code),
            ('account_type', 'in', ['expense', 'expense_direct_cost'])
        ], limit=1)
        
        if not expense:
            expense = Account.search([
                ('code', '=', '632'),
                ('account_type', 'in', ['expense', 'expense_direct_cost'])
            ], limit=1)
        
        if not expense:
            return 0, "Không tìm thấy tài khoản chi phí hợp lệ (6320 hoặc 632)"
        
        # Chỉ áp dụng cho danh mục real-time
        cats = Category.search([('property_valuation', '=', 'real_time')])
        updated = 0
        
        for cat in cats:
            try:
                # Chỉ set nếu trống HOẶC không phải loại expense
                current = cat.property_account_expense_categ_id
                if not current or current.account_type not in ['expense', 'expense_direct_cost']:
                    cat.write({'property_account_expense_categ_id': expense.id})
                    updated += 1
            except Exception as e:
                _logger.warning("Không thể set expense cho %s: %s", cat.display_name, e)
        
        return updated, len(cats)

    def _get_account_by_code(self, code):
        """Lấy account theo code - KHÔNG filter company_id"""
        Acc = self.env['account.account'].sudo()
        acc = Acc.search([('code', '=', str(code))], limit=1)
        
        if not acc:
            raise UserError(_("Không tìm thấy tài khoản mã %s") % code)
        return acc

    def _set_partner_default_properties(self, acc_ar, acc_ap):
        """Đặt AR/AP mặc định cho đối tác mới - Sử dụng set_param thay vì ir.property trực tiếp"""
        try:
            # Cách 1: Dùng ir.default (an toàn hơn)
            IrDefault = self.env['ir.default'].sudo()
            
            # Xóa default cũ nếu có
            IrDefault.search([
                ('field_id.model', '=', 'res.partner'),
                ('field_id.name', 'in', ['property_account_receivable_id', 'property_account_payable_id']),
                ('company_id', '=', self.env.company.id)
            ]).unlink()
            
            # Set default mới cho AR
            IrDefault.set(
                model_name='res.partner',
                field_name='property_account_receivable_id',
                value=acc_ar.id,
                company_id=self.env.company.id
            )
            
            # Set default mới cho AP
            IrDefault.set(
                model_name='res.partner',
                field_name='property_account_payable_id',
                value=acc_ap.id,
                company_id=self.env.company.id
            )
            
            _logger.info("Đã set default AR=%s, AP=%s qua ir.default", acc_ar.code, acc_ap.code)
            return True
            
        except Exception as e:
            _logger.warning("Không thể set default qua ir.default: %s. Bỏ qua bước này.", e)
            # Không raise error, chỉ warning
            return False

    def _update_existing_partners_ar_ap(self, acc_ar, acc_ap, mode='missing_only'):
        """Cập nhật AR/AP cho đối tác hiện có"""
        Partner = self.env['res.partner'].sudo()
        
        # Lấy tất cả partner (không filter company vì có thể là False)
        # Chỉ lấy partner không phải là contact (child của partner khác)
        partners = Partner.search([('parent_id', '=', False)])
        
        updated = 0
        errors = 0
        skipped = 0
        
        for p in partners:
            vals = {}
            
            if mode == 'all':
                # Cập nhật TẤT CẢ
                vals['property_account_receivable_id'] = acc_ar.id
                vals['property_account_payable_id'] = acc_ap.id
            elif mode == 'missing_only':
                # Chỉ cập nhật nếu trống
                try:
                    if not p.property_account_receivable_id:
                        vals['property_account_receivable_id'] = acc_ar.id
                    if not p.property_account_payable_id:
                        vals['property_account_payable_id'] = acc_ap.id
                except Exception:
                    # Nếu không đọc được property, skip
                    skipped += 1
                    continue
            
            if vals:
                try:
                    p.write(vals)
                    updated += 1
                except Exception as e:
                    _logger.warning("Không thể cập nhật partner %s: %s", p.display_name, e)
                    errors += 1
                    continue
        
        if errors > 0:
            _logger.warning("Có %d partner không cập nhật được", errors)
        if skipped > 0:
            _logger.info("Đã skip %d partner do không đọc được property", skipped)
        
        return updated, len(partners)

    def action_apply_config(self):
        """Thực thi cấu hình chính"""
        self.ensure_one()
        results = []
        
        try:
            # 1. Tạo tài khoản 1568/1569
            acc_input, c_in = self._ensure_account_exists(
                self.input_code, 
                f"{self.input_code} Tạm nhập (Interim Received)"
            )
            results.append(("✓ Tạo mới" if c_in else "○ Đã có") + f": TK {self.input_code}")

            acc_output, c_out = self._ensure_account_exists(
                self.output_code, 
                f"{self.output_code} Tạm xuất (Interim Delivered)"
            )
            results.append(("✓ Tạo mới" if c_out else "○ Đã có") + f": TK {self.output_code}")

            # 2. Kiểm tra tài khoản 1561
            Acc = self.env['account.account'].sudo()
            acc_valuation = Acc.search([('code', '=', self.valuation_code)], limit=1)
            
            if not acc_valuation:
                raise UserError(
                    _("Thiếu tài khoản %s (Stock Valuation). Hãy tạo trước.") 
                    % self.valuation_code
                )
            results.append(f"○ Đã có: TK {self.valuation_code} (Stock Valuation)")

            # 3. Tạo sổ nhật ký STK
            journal, c_j = self._ensure_stock_journal()
            results.append(("✓ Tạo mới" if c_j else "○ Đã có") + f": Sổ nhật ký {self.journal_code}")

            # 4. Áp dụng cho danh mục
            if self.apply_to_categories:
                up, total = self._apply_to_categories(acc_valuation, acc_input, acc_output, journal)
                results.append(f"✓ Áp dụng FIFO+Real-time: {up}/{total} danh mục")

            # 5. Set expense account
            if self.set_expense_account:
                upx, totalx = self._set_expense_accounts()
                if isinstance(upx, int):
                    results.append(f"✓ Set expense account: {upx}/{totalx} danh mục")
                else:
                    results.append(f"⚠ Expense: {totalx}")

            # 6. Lấy AR/AP account
            acc_ar = self._get_account_by_code(self.ar_code)
            acc_ap = self._get_account_by_code(self.ap_code)
            results.append(f"○ Tìm thấy: AR={self.ar_code}, AP={self.ap_code}")

            # 7. Set default AR/AP cho đối tác mới (optional, có thể fail)
            if self.set_partner_defaults:
                success = self._set_partner_default_properties(acc_ar, acc_ap)
                if success:
                    results.append(f"✓ Set default AR/AP cho đối tác mới")
                else:
                    results.append(f"⚠ Không set được default (không ảnh hưởng)")

            # 8. Cập nhật đối tác hiện có
            if self.update_existing_partners in ('missing_only', 'all'):
                upd, tot = self._update_existing_partners_ar_ap(
                    acc_ar, acc_ap, self.update_existing_partners
                )
                mode_text = {
                    'missing_only': 'chỉ cập nhật trống',
                    'all': 'cập nhật tất cả'
                }
                results.append(f"✓ Cập nhật partners: {upd}/{tot} ({mode_text[self.update_existing_partners]})")

            # Tạo HTML kết quả
            html = "<div style='font-family:monospace;padding:10px;'>"
            html += "<h3 style='color:green;margin-top:0;'>✓ Hoàn thành cấu hình</h3>"
            html += "<ul style='line-height:1.8;'>"
            for r in results:
                html += f"<li>{r}</li>"
            html += "</ul>"
            html += "<p style='color:#666;font-size:0.9em;margin-top:15px;'>"
            html += f"Company: {self.env.company.display_name}"
            html += "</p>"
            html += "</div>"
            
            self.result_message = html

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'dynamic.accounting.config.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': {'message_shown': True}
            }
            
        except UserError:
            raise
        except Exception as e:
            _logger.exception("Lỗi khi thực thi cấu hình")
            raise UserError(_("Lỗi không xác định: %s") % str(e))
