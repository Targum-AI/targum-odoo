import json
from odoo import http
from odoo.http import request


class TargumController(http.Controller):
    @http.route(
        "/targum_ai/products", type="http", auth="public", methods=["POST"], csrf=False
    )
    def receive_products(self):
        auth_header = request.httprequest.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return json.dumps({"error": "Bearer token required", "status": 401})

        try:
            token = auth_header[7:]

            api_key = (
                request.env["ir.config_parameter"]
                .sudo()
                .get_param("targum_ai.api_key", default="")
            )

            if not api_key:
                print("API key not configured in settings")
                return json.dumps({"error": "API key not configured", "status": 500})

            if token != api_key:
                print(f"Invalid token provided")
                return json.dumps({"error": "Invalid token", "status": 401})

            raw_data = request.httprequest.get_data(as_text=True)
            products_data = json.loads(raw_data)

            if not isinstance(products_data, list):
                return json.dumps(
                    {"error": "Expected array of products", "status": 400}
                )

            processed_products = []
            for product_data in products_data:
                try:
                    processed_product = self._process_product(product_data)
                    processed_products.append(processed_product)
                except Exception as e:
                    print(
                        f"Error processing product {product_data.get('id', 'unknown')}: {e}"
                    )
                    continue

            print(f"Successfully processed {len(processed_products)} products")
            return json.dumps(
                {"success": True, "processed_count": len(processed_products)}
            )

        except Exception as e:
            print(f"General error in receive_products: {e}")
            return json.dumps({"error": "Failed to process products", "status": 500})

    def _process_product(self, product_data):
        required_fields = ["id", "name", "merchant_id"]
        for field in required_fields:
            if field not in product_data:
                raise ValueError(f"Missing required field: {field}")

        merchant_id = product_data["merchant_id"]
        print(f"Processing product with merchant_id: {merchant_id})")

        product_template = (
            request.env["product.template"]
            .sudo()
            .search([("id", "=", merchant_id)], limit=1)
        )

        description_text = (
            product_data.get("description", {}).get("en", "")
            if isinstance(product_data.get("description"), dict)
            else product_data.get("description", "")
        )
        vals = {
            "name": (
                product_data["name"].get("en", "")
                if isinstance(product_data["name"], dict)
                else product_data["name"]
            ),
            "website_description": description_text,
        }

        if product_template:
            product_template.with_context(skip_webhook=True).write(vals)
            print(f"Updated product with merchant_id {product_data['merchant_id']}")
            return {"action": "updated", "product_id": product_template.id}
        else:
            new_product = (
                request.env["product.template"]
                .sudo()
                .with_context(skip_webhook=True)
                .create(vals)
            )
            print(f"Created new product with merchant_id {new_product.id}")
            return {"action": "created", "product_id": new_product.id}
