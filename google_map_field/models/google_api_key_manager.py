from odoo import models, api
from odoo.http import request


class GoogleApiKeyManager(models.AbstractModel):
    _name = "google.api.key.manager"
    _description = "Google API Key Manager"

    @api.model
    def get_google_api_key(self):
        """
        Returns the Google API key from system parameters.
        """
        return (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("google_api_key", default="")
        )

    @api.model
    def set_google_api_key(self, api_key):
        """
        Saves the Google API key to system parameters.
        """
        request.env["ir.config_parameter"].sudo().set_param(
            "google_api_key", api_key
        )
        return True