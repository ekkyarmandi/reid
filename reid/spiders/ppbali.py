from reid.spiders.base import BaseSpider
from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from itemloaders.processors import MapCompose
from datetime import datetime as dt
from reid.func import (
    get_lease_years,
    define_property_type,
    find_land_size,
    find_build_size,
    search_leasehold_years,
)
import re


class PpbaliSpider(BaseSpider):
    name = "ppbali"
    allowed_domains = ["ppbali.com"]
    start_urls = [
        "https://ppbali.com/search-result/?ref_id=&property_title=&property_type=villa",
        "https://ppbali.com/search-result/page/2/?ref_id&property_title&property_type=villa",
        "https://ppbali.com/search-result/page/3/?ref_id&property_title&property_type=villa",
        "https://ppbali.com/search-result/page/4/?ref_id&property_title&property_type=villa",
        "https://ppbali.com/search-result/page/5/?ref_id&property_title&property_type=villa",
        "https://ppbali.com/search-result/page/6/?ref_id&property_title&property_type=villa",
        "https://ppbali.com/search-result/page/7/?ref_id&property_title&property_type=villa",
        "https://ppbali.com/search-result/page/8/?ref_id&property_title&property_type=villa",
    ]

    def parse(self, response):
        items = response.css("div.box-result")
        for item in items:
            url = item.css("h4 a::attr(href)").get()
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(url, callback=self.parse_detail)
        for url in self.existing_urls:
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(url, callback=self.parse_detail)

    def parse_detail(self, response):
        ## lambda functions ##
        not_valid_contract = (
            lambda ctr: "free" not in ctr.lower() and "lease" not in ctr.lower()
        )

        ##  functions ##
        def last_css(key):
            results = response.css(
                f"div.quick-facts ul li:contains({key}) ::text"
            ).getall()
            if len(results) > 0:
                return results[-1].strip()
            return ""

        ## main logic ##
        loader = ItemLoader(item=PropertyItem(), selector=response)
        loader.add_value("source", "Paradise Property Group")
        loader.add_value("scraped_at", self.scraped_at)
        loader.add_value("url", response.url)
        loader.add_value("html", response.text)

        # contract_type
        contract_type = last_css("Status")
        result = re.search(r"\w+hold", contract_type)
        if result:
            contract_type = result.group().title()

        loader.add_value("availability_label", "Available")
        loader.add_css("title", "h1::text")
        loader.add_css("image_url", "#gallery-list div img::attr(src)")
        loader.add_css("property_id", "h3::text")
        loader.add_value("location", last_css("Location"))
        loader.add_value("land_size", last_css("Land"))
        loader.add_value("build_size", last_css("Build"))
        idr = response.css(
            "div.quick-facts ul li:contains(Price) span::attr(data-price_idr)"
        ).get()
        usd = response.css(
            "div.quick-facts ul li:contains(Price) span::attr(data-price_usd)"
        ).get()
        if idr:
            loader.add_value("price", idr)
            loader.add_value("currency", "IDR")
        elif usd:
            loader.add_value("price", usd)
            loader.add_value("currency", "USD")
        loader.add_value("contract_type", contract_type)
        loader.add_css(
            "property_type",
            "h1::text",
            MapCompose(define_property_type),
        )
        loader.add_css(
            "description",
            [
                "div.maincol > div ::text",
                "div.maincol > p ::text",
                "div.maincol li ::text",
            ],
        )

        # bathrooms
        b = {}
        table = response.css("#mainwrapper table tr")
        for j in range(len(table)):
            key = table[1].css(f"td:nth-child({j+1})::text").get()
            value = table[0].css(f"td:nth-child({j+1}) strong::text").get()
            b.update({key: value})
        loader.add_value("bedrooms", b.get("Beds"))
        loader.add_value("bathrooms", b.get("Baths"))

        # years
        status = response.css("div.quick-facts ul li:contains(Status)::text").get()
        if status:
            years = get_lease_years(status)
            loader.add_value("leasehold_years", years)

        # list_date
        c = {}
        sidecol = response.css("div.sidecol ul li")
        for li in sidecol:
            key, value = li.css("::text").getall()
            if key:
                key = key.replace(":", "")
                c.update({key: value})
        avail_date = c.get("Date Available", "").strip()
        if avail_date:
            try:
                date = dt.strptime(avail_date, "%d %B %Y")
                loader.add_value("listed_date", date.strftime("%m/%d/%y"))
            except:
                pass

        item = loader.load_item()

        # find the proper contract type and property type
        title = item.get("title", "")
        desc = item.get("description", "")
        if not_valid_contract(contract_type) and contract_type != "Rental":
            result = re.search(r"freehold|leasehold", desc, re.IGNORECASE)
            if result:
                item["contract_type"] = result.group().title()
            else:
                item["contract_type"] = "Other"

        # refind the years if it does not exists
        if not item.get("leasehold_years"):
            leasehold_years = search_leasehold_years(desc)
            if len(leasehold_years) > 0:
                item["leasehold_years"] = leasehold_years[0]

        # find missing land size in the description
        land_size = item.get("land_size")
        if not land_size:
            item["land_size"] = find_land_size(desc)

        # find missing build size in the description
        build_size = item.get("build_size")
        if not build_size:
            item["build_size"] = find_build_size(desc)

        if (
            item.get("price", 0) > 500000000
        ):  # filter price more than Rp 500,000,000 only
            yield item
