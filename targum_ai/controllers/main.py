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

        name_text = (
            product_data["name"].get("en", "")
            if isinstance(product_data["name"], dict)
            else product_data["name"]
        )

        vals = {
            "name": name_text,
            "description_sale": description_text,
        }

        if product_template:
            product_template.with_context(skip_webhook=True, skip_html_sanitize=True).write(vals)
            self._process_product_attributes(product_data, product_template)
            self._process_product_categories(product_data, product_template)
            self._process_product_keywords(product_data, product_template)
            print(f"Updated product with merchant_id {product_data['merchant_id']}")
            return {"action": "updated", "product_id": product_template.id}
        else:
            new_product = (
                request.env["product.template"]
                .sudo()
                .with_context(skip_webhook=True, skip_html_sanitize=True)
                .create(vals)
            )
            self._process_product_attributes(product_data, new_product)
            self._process_product_categories(product_data, new_product)
            self._process_product_keywords(product_data, new_product)
            print(f"Created new product with merchant_id {new_product.id}")
            return {"action": "created", "product_id": new_product.id}

    def _process_product_attributes(self, product_data, product_template):
        if "brands" in product_data and product_data["brands"]:
            for brand in product_data["brands"]:
                brand_name = brand.get("name", "")
                if brand_name:
                    self._create_attribute("Brand", brand_name, product_template)

        if "attributes" not in product_data:
            return

        for attr_data in product_data["attributes"]:
            attr_name = attr_data.get("name", {})
            if isinstance(attr_name, dict):
                attr_name = attr_name.get("en", "")

            if not attr_name:
                continue

            standardized_value = attr_data.get("standardized_text_value", {})
            if isinstance(standardized_value, dict):
                standardized_value = standardized_value.get("en", "")

            value = standardized_value or attr_data.get("value", "")
            unit = attr_data.get("unit", "")

            if unit:
                value = f"{value} {unit}"

            if not value or not value.strip():
                continue

            self._create_attribute(attr_name, value, product_template)

    def _create_attribute(self, attr_name, value, product_template):
        """Helper method to create product attributes"""
        attribute = (
            request.env["product.attribute"]
            .sudo()
            .search([("name", "=", attr_name)], limit=1)
        )

        if not attribute:
            attribute = (
                request.env["product.attribute"]
                .sudo()
                .create({"name": attr_name, "display_type": "select"})
            )

        attr_value = (
            request.env["product.attribute.value"]
            .sudo()
            .search(
                [("attribute_id", "=", attribute.id), ("name", "=", value)], limit=1
            )
        )

        if not attr_value:
            attr_value = (
                request.env["product.attribute.value"]
                .sudo()
                .create({"attribute_id": attribute.id, "name": value})
            )

        attr_line = product_template.attribute_line_ids.filtered(
            lambda l: l.attribute_id.id == attribute.id
        )

        if not attr_line:
            request.env["product.template.attribute.line"].sudo().create(
                {
                    "product_tmpl_id": product_template.id,
                    "attribute_id": attribute.id,
                    "value_ids": [(6, 0, [attr_value.id])],
                }
            )
        else:
            if attr_value.id not in attr_line.value_ids.ids:
                attr_line.write({"value_ids": [(4, attr_value.id)]})

    def _process_product_categories(self, product_data, product_template):
        """Process and assign product categories using Odoo's category system"""
        if "categories" not in product_data:
            return

        categories = product_data["categories"]
        if not categories:
            return

        main_cat_name = None
        for cat in categories:
            cat_name = cat.get("name", {})
            if isinstance(cat_name, dict):
                cat_name = cat_name.get("en", "")
            if cat_name and not main_cat_name:
                main_cat_name = cat_name
                break

        if main_cat_name:
            category = (
                request.env["product.category"]
                .sudo()
                .search([("name", "ilike", main_cat_name)], limit=1)
            )

            if not category:
                category = (
                    request.env["product.category"]
                    .sudo()
                    .create({"name": main_cat_name})
                )

            product_template.write({"categ_id": category.id})

        try:
            public_categories = []
            for cat in categories:
                cat_name = cat.get("name", {})
                if isinstance(cat_name, dict):
                    cat_name = cat_name.get("en", "")

                if cat_name:
                    pub_cat = (
                        request.env["product.public.category"]
                        .sudo()
                        .search([("name", "ilike", cat_name)], limit=1)
                    )

                    if not pub_cat:
                        pub_cat = (
                            request.env["product.public.category"]
                            .sudo()
                            .create({"name": cat_name})
                        )

                    public_categories.append(pub_cat.id)

            if public_categories:
                product_template.write(
                    {"public_categ_ids": [(6, 0, public_categories)]}
                )
        except Exception:
            pass

    def _process_product_keywords(self, product_data, product_template):
        """Process keywords and create/assign Product Template Tags"""
        if "keywords" not in product_data:
            return

        keywords = product_data["keywords"]
        if not keywords:
            return

        tag_ids = []
        for keyword_data in keywords:
            keyword = keyword_data.get("keyword", "")
            if not keyword or not keyword.strip():
                continue

            try:
                tag = (
                    request.env["product.tag"]
                    .sudo()
                    .search([("name", "=ilike", keyword.strip())], limit=1)
                )

                if not tag:
                    tag = (
                        request.env["product.tag"]
                        .sudo()
                        .create({"name": keyword.strip()})
                    )

                tag_ids.append(tag.id)
            except Exception as e:
                print(f"Error processing tag '{keyword}': {str(e)}")
                continue

        print(f"Assigning tags: {tag_ids}")
        if tag_ids:
            try:
                product_template.write({"tag_ids": [(6, 0, tag_ids)]})
            except Exception as e:
                print(f"Error assigning tags to product: {str(e)}")

    @http.route(
        "/targum_ai/sync_all_products", type="json", auth="user", methods=["POST"]
    )
    def sync_all_products(self):
        try:
            batch_size = 50
            products = request.env["product.template"].search([])
            total_products = len(products)

            if total_products == 0:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "message": "No products found to sync.",
                        "type": "warning",
                    },
                }

            synced_count = 0
            failed_count = 0

            for i in range(0, total_products, batch_size):
                batch = products[i : i + batch_size]
                for product in batch:
                    try:
                        product.with_context(skip_webhook=False)._send_product(
                            product, "update"
                        )
                        synced_count += 1
                    except Exception as e:
                        failed_count += 1
                        print(f"Failed to sync product {product.name}: {str(e)}")

                request.env.cr.commit()

            message = f"Sync completed: {synced_count} products synced"
            if failed_count > 0:
                message += f", {failed_count} failed"

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "message": message,
                    "type": "success" if failed_count == 0 else "warning",
                },
            }
        except Exception as e:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "message": f"Error during sync: {str(e)}",
                    "type": "danger",
                },
            }
