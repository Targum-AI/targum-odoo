import json
from odoo import http
from odoo.http import request


class TargumController(http.Controller):
    @http.route(
        "/targum_ai/products", type="http", auth="none", methods=["POST"], csrf=False
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
                print("API key not configured in settings", flush=True)
                return json.dumps({"error": "API key not configured", "status": 500})

            if token != api_key:
                print(f"Invalid token provided", flush=True)
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
                        f"Error processing product {product_data.get('id', 'unknown')}: {e}",
                        flush=True,
                    )
                    continue

            print(
                f"Successfully processed {len(processed_products)} products", flush=True
            )
            return json.dumps(
                {"success": True, "processed_count": len(processed_products)}
            )

        except Exception as e:
            print(f"General error in receive_products: {e}", flush=True)
            return json.dumps({"error": "Failed to process products", "status": 500})

    def _process_product(self, product_data):
        required_fields = ["id", "name", "merchant_id"]
        for field in required_fields:
            if field not in product_data:
                raise ValueError(f"Missing required field: {field}")

        merchant_id = product_data["merchant_id"]
        print(f"Processing product with merchant_id: {merchant_id})", flush=True)

        product_template = (
            request.env["product.template"]
            .sudo()
            .search([("id", "=", merchant_id)], limit=1)
        )

        name_data = product_data.get("name", {})
        description_data = product_data.get("description", {})

        if isinstance(name_data, dict):
            name_text = name_data.get("en", "") or next(iter(name_data.values()), "")
        else:
            name_text = name_data or ""

        if isinstance(description_data, dict):
            description_text = description_data.get("en", "") or next(
                iter(description_data.values()), ""
            )
        else:
            description_text = description_data or ""

        if product_template:
            self._save_product_translations(product_data, product_template)
            self._process_product_attributes(product_data, product_template)
            self._process_product_categories(product_data, product_template)
            self._process_product_keywords(product_data, product_template)
            print(
                f"Updated product with merchant_id {product_data['merchant_id']}",
                flush=True,
            )
            return {"action": "updated", "product_id": product_template.id}
        else:
            minimal_vals = {
                "name": name_text or "Temp Name",
                "description_sale": description_text,
            }
            new_product = (
                request.env["product.template"]
                .sudo()
                .with_context(skip_webhook=True, skip_html_sanitize=True)
                .create(minimal_vals)
            )

            self._save_product_translations(product_data, new_product)
            self._process_product_attributes(product_data, new_product)
            self._process_product_categories(product_data, new_product)
            self._process_product_keywords(product_data, new_product)
            print(f"Created new product with merchant_id {new_product.id}", flush=True)
            return {"action": "created", "product_id": new_product.id}

    def _process_product_attributes(self, product_data, product_template):
        product_template.attribute_line_ids.unlink()

        attributes_to_create = {}

        if "brands" in product_data and product_data["brands"]:
            for brand in product_data["brands"]:
                brand_name = brand.get("name", "")
                if brand_name:
                    if "Brand" not in attributes_to_create:
                        attributes_to_create["Brand"] = []
                    attributes_to_create["Brand"].append(brand_name)

        if "attributes" in product_data:
            for attr_data in product_data["attributes"]:
                attr_name_data = attr_data.get("name", {})

                if isinstance(attr_name_data, dict):
                    attr_name = attr_name_data.get("en", "") or next(
                        iter(attr_name_data.values()), ""
                    )
                else:
                    attr_name = attr_name_data or ""

                if not attr_name:
                    continue

                standardized_value = attr_data.get("standardized_text_value", {})
                if isinstance(standardized_value, dict):
                    standardized_value = standardized_value.get("en", "") or next(
                        iter(standardized_value.values()), ""
                    )

                value = standardized_value or attr_data.get("value", "")

                if not value or not value.strip():
                    continue

                if attr_name not in attributes_to_create:
                    attributes_to_create[attr_name] = {
                        "values": [],
                        "name_data": attr_name_data,
                    }
                attributes_to_create[attr_name]["values"].append(value)

        for attr_name, attr_info in attributes_to_create.items():
            self._create_attribute(
                attr_name, attr_info["values"], product_template, attr_info["name_data"]
            )

    def _create_attribute(self, attr_name, values, product_template, name_data=None):
        """Helper method to create product attributes with all values at once"""
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

        if name_data and isinstance(name_data, dict):
            self._save_record_translations(name_data, attribute)

        value_ids = []
        for value in values:
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

            value_ids.append(attr_value.id)

        request.env["product.template.attribute.line"].sudo().create(
            {
                "product_tmpl_id": product_template.id,
                "attribute_id": attribute.id,
                "value_ids": [(6, 0, value_ids)],
            }
        )

    def _process_product_categories(self, product_data, product_template):
        """Process and assign product categories using Odoo's category system"""
        if "categories" not in product_data:
            return

        categories = product_data["categories"]
        if not categories:
            return

        main_cat_name = None
        main_cat_name_data = None
        for cat in categories:
            cat_name_data = cat.get("name", {})
            if isinstance(cat_name_data, dict):
                cat_name = cat_name_data.get("en", "") or next(
                    iter(cat_name_data.values()), ""
                )
            else:
                cat_name = cat_name_data or ""
            if cat_name and not main_cat_name:
                main_cat_name = cat_name
                main_cat_name_data = cat_name_data
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

            if main_cat_name_data and isinstance(main_cat_name_data, dict):
                self._save_record_translations(main_cat_name_data, category)

            product_template.with_context(skip_webhook=True).write(
                {"categ_id": category.id}
            )

        try:
            public_categories = []
            for cat in categories:
                cat_name_data = cat.get("name", {})
                if isinstance(cat_name_data, dict):
                    cat_name = cat_name_data.get("en", "") or next(
                        iter(cat_name_data.values()), ""
                    )
                else:
                    cat_name = cat_name_data or ""

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

                    if cat_name_data and isinstance(cat_name_data, dict):
                        self._save_record_translations(cat_name_data, pub_cat)

                    public_categories.append(pub_cat.id)

            if public_categories:
                product_template.with_context(skip_webhook=True).write(
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
                print(f"Error processing tag '{keyword}': {str(e)}", flush=True)
                continue

        print(f"Assigning tags: {tag_ids}", flush=True)
        if tag_ids:
            try:
                product_template.with_context(skip_webhook=True).write(
                    {"product_tag_ids": [(6, 0, tag_ids)]}
                )
            except Exception as e:
                print(f"Error assigning tags to product: {str(e)}", flush=True)

    def _save_product_translations(self, product_data, product_template):
        """Save product name and description translations for all received languages"""
        try:
            name_data = product_data.get("name", {})
            description_data = product_data.get("description", {})

            if not isinstance(name_data, dict) and not isinstance(
                description_data, dict
            ):
                return

            available_languages = (
                request.env["res.lang"].sudo().search([("active", "=", True)])
            )

            lang_codes = [lang.code for lang in available_languages]

            if isinstance(name_data, dict):
                for targum_lang, translated_name in name_data.items():
                    matching_lang = None
                    for odoo_lang in lang_codes:
                        if odoo_lang.startswith(targum_lang + "_"):
                            matching_lang = odoo_lang
                            break

                    if matching_lang and translated_name and translated_name.strip():
                        try:
                            product_template.with_context(
                                lang=matching_lang,
                                skip_webhook=True,
                                skip_html_sanitize=True,
                            ).write({"name": translated_name})
                            print(
                                f"Saved name translation for {targum_lang} -> {matching_lang}: {translated_name}",
                                flush=True,
                            )
                        except Exception as e:
                            print(
                                f"Error saving name translation for {targum_lang} -> {matching_lang}: {e}",
                                flush=True,
                            )

            if isinstance(description_data, dict):
                for targum_lang, translated_desc in description_data.items():
                    matching_lang = None
                    for odoo_lang in lang_codes:
                        if odoo_lang.startswith(targum_lang + "_"):
                            matching_lang = odoo_lang
                            break

                    if matching_lang and translated_desc and translated_desc.strip():
                        try:
                            product_template.with_context(
                                lang=matching_lang,
                                skip_webhook=True,
                                skip_html_sanitize=True,
                            ).write({"description_sale": translated_desc})
                            print(
                                f"Saved description translation for {targum_lang} -> {matching_lang}: {translated_desc[:50]}...",
                                flush=True,
                            )
                        except Exception as e:
                            print(
                                f"Error saving description translation for {targum_lang} -> {matching_lang}: {e}",
                                flush=True,
                            )

        except Exception as e:
            print(f"Error in _save_product_translations: {str(e)}", flush=True)

    def _save_record_translations(self, name_data, record):
        """Save translations for any Odoo record (category, attribute, etc.)"""
        if not isinstance(name_data, dict):
            return

        try:
            available_languages = (
                request.env["res.lang"].sudo().search([("active", "=", True)])
            )
            lang_codes = [lang.code for lang in available_languages]

            for targum_lang, translated_name in name_data.items():
                matching_lang = None
                for odoo_lang in lang_codes:
                    if odoo_lang.startswith(targum_lang + "_"):
                        matching_lang = odoo_lang
                        break

                if matching_lang and translated_name and translated_name.strip():
                    try:
                        record.with_context(lang=matching_lang).write(
                            {"name": translated_name}
                        )
                        print(
                            f"Saved translation for {record._name} ({targum_lang} -> {matching_lang}): {translated_name}",
                            flush=True,
                        )
                    except Exception as e:
                        print(
                            f"Error saving translation for {record._name} ({targum_lang}): {e}",
                            flush=True,
                        )
        except Exception as e:
            print(f"Error in _save_record_translations: {str(e)}", flush=True)

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
                        print(
                            f"Failed to sync product {product.name}: {str(e)}",
                            flush=True,
                        )

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
