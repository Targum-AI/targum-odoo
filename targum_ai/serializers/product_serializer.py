from odoo.http import request


class ProductSerializer:
    @staticmethod
    def serialize_product(
        product, include_variants=True, include_images=True, base_url=None
    ):
        if base_url is None and hasattr(request, "httprequest"):
            base_url = request.httprequest.url_root.rstrip("/")

        images = []
        if include_images and product.image_1920 and base_url:
            images.append(
                f"{base_url}/web/image/product.template/{product.id}/image_1920"
            )

        category = {
            "id": product.categ_id.id if product.categ_id else None,
            "name": product.categ_id.name if product.categ_id else "",
        }

        attributes = []
        for line in product.attribute_line_ids:
            for value in line.value_ids:
                attr_data = {
                    "id": line.attribute_id.id,
                    "name": line.attribute_id.name,
                    "value": value.name,
                }

                if hasattr(value, "unit") and value.unit:
                    attr_data["unit"] = value.unit
                attributes.append(attr_data)

        metadata = []
        if product.default_code:
            metadata.append({"key": "sku", "value": product.default_code})
        if product.barcode:
            metadata.append({"key": "ean", "value": product.barcode})
        if hasattr(product, "weight") and product.weight:
            metadata.append({"key": "weight", "value": str(product.weight)})
        if hasattr(product, "volume") and product.volume:
            metadata.append({"key": "volume", "value": str(product.volume)})

        product_data = {
            "id": product.id,
            "name": product.name,
            "description": product.website_description
            or product.description_sale
            or product.description
            or "",
            "images": images,
            "category": category,
            "attributes": attributes,
            "metadata": metadata,
        }

        if include_variants:
            variants = []
            if product.product_variant_ids:
                for variant in product.product_variant_ids:
                    variant_data = {
                        "id": variant.id,
                        "name": variant.display_name,
                        "sku": variant.default_code or "",
                        "barcode": variant.barcode or "",
                        "price": variant.list_price,
                        "attributes": [],
                    }

                    for value in variant.product_template_attribute_value_ids:
                        variant_data["attributes"].append(
                            {
                                "id": value.attribute_id.id,
                                "name": value.attribute_id.name,
                                "value": value.name,
                            }
                        )

                    variants.append(variant_data)

            product_data["variants"] = variants

        return product_data

    @staticmethod
    def build_webhook_data(product, action, **kwargs):
        webhook_kwargs = {"include_variants": False, "include_images": False, **kwargs}

        product_data = ProductSerializer.serialize_product(product, **webhook_kwargs)

        product_data["metadata"].append({"key": "action", "value": action})

        return {
            "products": [product_data],
            "embed_products": False,
            "automatic_return": False,
            "template": 5,
        }
