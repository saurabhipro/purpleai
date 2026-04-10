{
    "name": "AI Core",
    "version": "1.0.0",
    "summary": "Centralized AI configuration and services for Memo AI and Purple AI modules.",
    "author": "Your Company",
    "category": "Tools",
    "depends": ["base", "base_setup"],
    "data": [
        "views/ai_settings_views.xml"
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
    "website": "https://example.com",
    "description": """\nAI Core module abstracts AI provider settings, embedding and call utilities.
It allows other Odoo modules to reuse the same configuration without duplication.
"""
}
