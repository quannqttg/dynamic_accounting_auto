# -*- coding: utf-8 -*-
{
    'name': 'Dynamic Accounting Config',
    'version': '18.0.1.1.0',
    'category': 'Accounting',
    'summary': 'FIFO + Real-time inventory valuation, stock journal, expense account, AR/AP defaults (1311/3311)',
    'description': """
Odoo 18 Community auto configuration:
- Create missing 1568/1569 (interim accounts)
- Create Stock Valuation Journal (Misc)
- Apply FIFO + Real-time valuation on product categories
- Set expense account 6320 at category level (if missing)
- Set default AR/AP (1311/3311) via ir.property and optionally update existing partners
""",
    'author': 'Nguyen An PC',
    'website': 'https://nguyenanpc.vn',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'stock',
        'stock_account',
        'product',
        'contacts',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/wizard_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
