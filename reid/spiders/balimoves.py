import scrapy
import re
from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from reid.spiders.base import BaseSpider
from itemloaders.processors import MapCompose
from reid.func import (
    find_idr,
    find_usd,
    get_lease_years,
    grab_first_word,
    define_property_type,
    identify_currency,
)
from reid.customs.balimoves import fa_remover


class BaliMovesSpider(BaseSpider):
    name = "balimoves"
    allowed_domains = ["balimoves.com"]
    start_urls = [
        "https://www.balimoves.com/buy/leasehold/",
        "https://www.balimoves.com/buy/ubud/",
        "https://www.balimoves.com/buy/sanur/",
        "https://www.balimoves.com/buy/canggu/",
        "https://www.balimoves.com/land/",
    ]

    def parse(self, response):
        # collect urls
        urls = response.css("a:contains('View this')::attr(href)").getall()
        for url in urls:
            if not url in self.visited_urls:
                self.visited_urls.append(url)
                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    errback=self.handle_error,
                )
        # iterate existing urls
        for url in self.existing_urls:
            if not url in self.visited_urls:
                self.visited_urls.append(url)
                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    errback=self.handle_error,
                )
        # do pagination
        pages = response.css("a.page-numbers::Text").re("\d{1}")
        if pages:
            max_page = max(map(int, pages))
            # get response url path and ignore the query params
            origin_url = response.url.split("?")[0]
            for i in range(2, max_page + 1):
                next_url = origin_url + "?fwp_paged=" + str(i)
                yield scrapy.Request(next_url, callback=self.parse)

    def parse_detail(self, response):
        loader = ItemLoader(item=PropertyItem(), selector=response)
        loader.add_value("source", "Bali Moves")
        loader.add_value("scraped_at", self.scraped_at)
        loader.add_value("url", response.url)
        loader.add_value("html", response.text)

        ids = response.css("::attr(data-node)").getall()
        selectors = [
            dict(
                value=f"div#fl-icon-text-{node} p::Text",
                name=f"div.fl-node-{node} i::attr(class)",
            )
            for node in ids
        ]
        values = {
            _id: dict(
                name=fa_remover(response.css(css["name"]).get()),
                value=response.css(css["value"]).get(),
            )
            for _id, css in zip(ids, selectors)
        }
        items = {k: v for k, v in values.items() if v["value"] is not None}
        table = {}
        for item in items.values():
            key = item["name"]
            value = item["value"]
            if key not in table:
                table[key] = value

        loader.add_css("title", "h1 span::Text")
        loader.add_css(
            "description",
            "div.fl-module-content.fl-node-content > div.fl-rich-text > p:not(:contains(Adyatama)):not(:contains(ID))::Text",
        )
        loader.add_css(
            "image_url",
            "div#jig1 a:has(img)::attr(href),img[src*=balimoves]:not([src*=logo])::attr(src)",
        )
        loader.add_css(
            "property_type",
            "h1 span::Text",
            MapCompose(define_property_type),
        )
        loader.add_css(
            "currency",
            "div.fl-html div::Text",
            MapCompose(identify_currency),
        )
        if loader.get_output_value("currency") == "IDR":
            loader.add_css("price", "div.fl-html div::Text", MapCompose(find_idr))
        else:
            loader.add_css("price", "div.fl-html div::Text", MapCompose(find_usd))

        loader.add_value("property_id", table.get("hashtag"))
        loader.add_value("location", table.get("map-marker-alt"))
        loader.add_value("bedrooms", table.get("bed"))
        loader.add_value("bathrooms", table.get("shower"))
        loader.add_value(
            "land_size",
            table.get("expand-arrows-alt"),
            MapCompose(lambda v: v.replace(",", ".")),
        )
        loader.add_value(
            "build_size",
            table.get("expand"),
            MapCompose(lambda v: v.replace(",", ".")),
        )
        loader.add_value(
            "contract_type",
            table.get("copy"),
            MapCompose(grab_first_word),
        )

        ## default value ##
        loader.add_value("availability_label", "Available")

        item = loader.load_item()

        ## if else attribute value ##
        price_title = response.css("div.fl-html div::Text").get()
        if re.search(r"freehold", price_title, re.IGNORECASE):
            item["contract_type"] = "Freehold"

        per = re.findall(r"\/\w+", price_title)
        per = list(set(per))
        joined_per = " ".join(per)

        ## define rental contract type ##
        if "month" in joined_per or "year" in joined_per:
            item["contract_type"] = "Rent"

        bedrooms = item.get("bedrooms")
        if not bedrooms:
            item["property_type"] = "Land"

        contract_type = item.get("contract_type", "")
        if contract_type == "Leasehold":
            item["leasehold_years"] = get_lease_years(price_title)

        ## alternative value ##
        if not price_title or price_title.strip() == "":
            item["availability_label"] = "Sold"

        ## calculate price based on land_size ##
        if "are" in joined_per or "m2" in joined_per:
            price_idr = item.get("price", 0)
            land_size = item["land_size"]
            price_idr = -1 if not price_idr else price_idr
            if "are" in joined_per and land_size > 0:
                per_land = land_size / 100
                price_idr = price_idr * per_land
            elif "m2" in joined_per and land_size > 0:
                result = re.search(r"\d+", joined_per)
                if result:
                    sqm = int(result.group(0))
                    per_land = land_size / sqm
                    price_idr = price_idr * per_land
            ## validate the price as None instead of 0 ##
            item["price"] = None if int(price_idr) == 0 else item["price"]

        yield item
