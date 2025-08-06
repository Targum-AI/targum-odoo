import requests
from odoo import models, fields, api
from ..serializers.product_serializer import ProductSerializer


class ProductTemplate(models.Model):
    _inherit = "product.template"

    merchant_id = fields.Char(string="Merchant ID", help="External merchant identifier")

    @api.model
    def create(self, vals):
        print(f"New product created: {vals}")
        product = super(ProductTemplate, self).create(vals)
        if not self.env.context.get("skip_webhook"):
            self._send_webhook(product, "create")
        return product

    def write(self, vals):
        print(f"Product updated: {vals}")
        result = super(ProductTemplate, self).write(vals)
        if not self.env.context.get("skip_webhook"):
            for product in self:
                print(f"Sending product to Targum: {product.name}")
                self._send_webhook(product, "update")
        return result

    def _send_webhook(self, product, action):
        try:
            integration_secret = (
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("targum_ai.integration_secret")
            )
            targum_instance_url = (
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("targum_ai.instance_url")
            )

            if not integration_secret or not targum_instance_url:
                print("Webhook not configured - missing secret or instance URL")
                return

            if "localhost" in targum_instance_url:
                targum_instance_url = targum_instance_url.replace(
                    "localhost", "host.docker.internal"
                )

            products_api_url = f"{targum_instance_url.rstrip('/')}/api/products"
            product_data = ProductSerializer.build_webhook_data(product, action)

            print(f"Sending product to: {products_api_url} with data: {product_data}")

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {integration_secret}",
            }

            response = requests.post(
                products_api_url, json=product_data, headers=headers, timeout=5
            )

            print(f"Targum response: {response.status_code}")

            if response.status_code >= 400:
                print(
                    f"Webhook failed with status {response.status_code}: {response.text}"
                )
        except requests.exceptions.ConnectionError as e:
            print(
                f"Webhook connection error: {str(e)}. Make sure your API is running and accessible from Docker container."
            )
        except Exception as e:
            print(f"Webhook error: {str(e)}")
