from urllib.parse import urlencode
from models.error import Error
from reid.database import get_db
from itemloaders.processors import MapCompose
from reid.spiders.base import BaseSpider
from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from reid.func import (
    count_lease_years,
    get_lease_years,
)
import jmespath
import traceback
import scrapy
import math
import json
import re


class LuxindopropertySpider(BaseSpider):
    name = "luxindoproperty"
    allowed_domains = ["luxindoproperty.com", "usrrhfmmqhzdufinynbj.supabase.co"]
    start_urls = ["https://www.luxindoproperty.com/properties"]

    def parse(self, response):
        total = response.css("p:contains(Results)").re_first(r"\d{2,4}")
        if not total:
            raise scrapy.exceptions.CloseSpider(
                "Failed to get the total number of properties"
            )
        total = int(total)
        limit = 500
        offset = 0
        for i in range(1, math.ceil(total / limit) + 1):
            offset = (i - 1) * limit
            querystring = {
                "select": "id,slug,sku,type,ownership,prestige,price,currency,area_1,area_2,created_at,image:media(*),images:properties_images(file:media(*)),properties_locales(title),spaces:properties_spaces(title,value),plans:properties_plans(title,value)",
                "visible": "eq.true",
                "order": "created_at.desc",
                "offset": str(offset),
                "limit": str(limit),
            }
            yield scrapy.Request(
                url=f"https://usrrhfmmqhzdufinynbj.supabase.co/rest/v1/properties?{urlencode(querystring)}",
                headers={
                    "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVzcnJoZm1tcWh6ZHVmaW55bmJqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mjg2MDQyMzMsImV4cCI6MjA0NDE4MDIzM30.6tnNjCnv6LA-AwPmjg7E0lOGblQ63K3AVOf8hXWjDuk",
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                },
                callback=self.parse_data,
            )

    def parse_data(self, response):
        items = response.json()
        for item in items:
            slug = item.get("slug")
            yield scrapy.Request(
                url=f"https://www.luxindoproperty.com/{slug}",
                meta={"json_data": item},
                callback=self.parse_detail,
            )

    def parse_detail(self, response):
        loader = ItemLoader(item=PropertyItem(), selector=response)
        data = response.meta.get("json_data")
        loader.add_value("source", "Luxindo Property")
        loader.add_value("url", response.url)
        loader.add_value("scraped_at", self.scraped_at)
        loader.add_value("html", response.text)
        loader.add_value("availability_label", "Available")

        if data:
            loader.add_value("json", json.dumps(data))
            loader.add_value("property_id", data.get("sku"))
            loader.add_value(
                "title", jmespath.search("properties_locales[0].title", data)
            )
            loader.add_value(
                "image_url", jmespath.search("image.thumbnail_u_r_l", data)
            )
        try:
            loc = data.get("area_2")
            loader.add_value("location", data.get("area_1", loc))
            loader.add_value("price", data.get("price", -1))
            loader.add_value("currency", data.get("currency", "IDR"))
            loader.add_value("property_type", data.get("type"))

            # contract type
            # if not property_type:
            #     property_type = define_property_type(title)

            contract_type = data.get("ownership", "Freehold")
            if not contract_type:
                contract_type = "Freehold"
            loader.add_value("contract_type", contract_type)
            loader.add_value("listed_date", data.get("created_at"))

            spaces = data.get("spaces", [])
            for i in spaces:
                if not i["title"]:
                    continue
                if re.search(r"land", i["title"], re.IGNORECASE):
                    loader.add_value("land_size", i["value"])
                    continue
                if re.search(r"lease", contract_type, re.IGNORECASE):
                    if re.search(r"valid", i["title"], re.IGNORECASE):
                        loader.add_value(
                            "leasehold_years", i["value"], MapCompose(get_lease_years)
                        )
                        continue
                    elif re.search(r"lease", i["title"], re.IGNORECASE):
                        loader.add_value(
                            "leasehold_years", i["value"], MapCompose(count_lease_years)
                        )
                        continue

            plans = data.get("plans", [])
            for i in plans:
                if re.search(r"built", i["title"], re.IGNORECASE):
                    loader.add_value("build_size", i["value"])
                    continue
                if re.search(r"bedroom", i["title"], re.IGNORECASE):
                    loader.add_value("bedrooms", i["value"])
                    continue
                if re.search(r"bathroom", i["title"], re.IGNORECASE):
                    loader.add_value("bathrooms", i["value"])
                    continue

            loader.add_css(
                "description",
                "div.sourceSansPro:has(p) ::Text",
            )

            item = loader.load_item()
            yield item

        except Exception as err:
            error = Error(
                url=response.url,
                source="Spider",
                error_message=str(err),
            )
            tb = traceback.format_exc()
            error.error_message += f"\nTraceback:\n{tb}"
            db = next(get_db())
            try:
                db.add(error)
                db.commit()
            except Exception as e:
                db.rollback()
                self.logger.error(f"Error adding error to database: {e}")
