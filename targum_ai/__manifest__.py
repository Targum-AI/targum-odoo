{
    "name": "Targum AI Integration",
    "version": "17.0.0.1.8",
    "summary": "Import products to Targum AI for enrichment and sync back to Odoo",
    "description": """
Targum AI Integration
=====================

This module enables seamless product data enrichment workflow between Odoo and Targum AI:

* Import products from Odoo to Targum AI platform
* AI-powered product data enrichment and optimization
* Sync enhanced products back to Odoo
* Automated product data improvement

Features:
---------
* Automatic product sync to Targum AI
* AI product data enrichment
* Easy setup and configuration

Requirements:
-------------
* Valid Targum AI API credentials
* Odoo 17.0 or later
    """,
    "author": "Targum AI",
    "website": "https://targum.ai",
    "category": "Sales/Sales",
    "license": "LGPL-3",
    "depends": ["base", "base_setup", "website_sale"],
    "application": True,
    "installable": True,
    "auto_install": False,
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "images": [
        "static/description/icon.png",
    ],
    "price": 0.00,
    "currency": "EUR",
}
