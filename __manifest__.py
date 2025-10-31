{
    "name": "Dynamic Accounting (CE)",
    "summary": "Auto apply inventory valuation setup + quick COGS/P&L helpers (Community Edition)",
    "version": "0.1.2",
    "author": "Quan Nguyen / ChatGPT",
    "license": "LGPL-3",
    "website": "",
    "category": "Accounting",
    "depends": ["base", "account", "stock", "sale", "purchase"],
    "data": [
        "security/ir.model.access.csv",
        "views/wizard_views.xml",   # action first
        "views/menu.xml",           # menu AFTER action
        # "data/cron.xml",          # uncomment when you want cron
    ],
    "installable": True,
    "application": False,
}
