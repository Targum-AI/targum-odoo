import secrets
import string
from odoo import fields, models, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    integration_secret = fields.Char(
        string='Integration Secret',
        config_parameter='targum_ai.integration_secret',
        help='Secret key for authenticating webhooks to Targum'
    )
    
    targum_instance_url = fields.Char(
        string='Targum Instance URL',
        config_parameter='targum_ai.instance_url',
        default='http://localhost:3000',
        help='Base URL of your Targum instance (e.g., https://api.targum.ai)'
    )
    
    api_key = fields.Char(
        string='API Key',
        config_parameter='targum_ai.api_key',
        help='API key for Targum AI integration'
    )
    
    @api.model
    def _generate_api_key(self):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))
    
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        existing_api_key = self.env['ir.config_parameter'].sudo().get_param('targum_ai.api_key')

        if not existing_api_key:
            api_key = self._generate_api_key()
            self.env['ir.config_parameter'].sudo().set_param('targum_ai.api_key', api_key)
            res['api_key'] = api_key
        return res
