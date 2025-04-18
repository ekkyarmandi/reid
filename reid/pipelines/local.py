import re


class CheckMissingFieldsPipeline:
    def process_item(self, item, spider):
        required_fields = [
            "property_id",
            "listed_date",
            "title",
            "location",
            "contract_type",
            "property_type",
            "leasehold_years",
            "longitude",
            "latitude",
            "bedrooms",
            "bathrooms",
            "land_size",
            "build_size",
            "price",
            "currency",
            "image_url",
            "availability_label",
            "sold_at",
            "description",
            "is_off_plan",
        ]

        missing_fields = [
            field
            for field in required_fields
            if field not in item or item[field] is None or item[field] == ""
        ]
        contract_type = item.get("contract_type", "").lower()
        if not re.search(r"lease", contract_type, re.IGNORECASE):
            missing_fields = list(
                filter(lambda field: field != "leasehold_years", missing_fields)
            )
        if re.search(r"available", item.get("availability_label", ""), re.IGNORECASE):
            missing_fields = list(
                filter(lambda field: field != "sold_at", missing_fields)
            )

        return dict(missing_fields=missing_fields)
