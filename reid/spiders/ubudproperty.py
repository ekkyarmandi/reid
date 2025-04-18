import scrapy
from urllib.parse import urljoin
from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from itemloaders.processors import MapCompose
from reid.database import get_db
from models.error import Error
import re
import traceback
from reid.spiders.base import BaseSpider
from reid.func import (
    define_property_type,
    find_build_size,
    find_idr,
    find_land_size,
    find_usd,
)

from reid.customs.ubudproperty import (
    find_code,
    extract_publish_date,
    find_leasehold_years,
)


class UbudPropertySpider(BaseSpider):
    name = "ubudproperty"
    allowed_domains = ["ubudproperty.com"]
    start_urls = [
        "https://ubudproperty.com/listing-villaforsale",
        "https://ubudproperty.com/listing-landforsale",
    ]

    def parse(self, response):
        # collect urls
        codes = response.css("a:contains(Detail)::attr(href)").getall()
        urls = list(map(lambda x: urljoin(response.url, x), codes))
        urls = list(filter(lambda x: x not in self.visited_urls, urls))
        urls = list(filter(lambda x: x not in self.existing_urls, urls))
        for url in urls:
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield scrapy.Request(
                    url, callback=self.parse_detail, errback=self.handle_error
                )

        # fetch existing urls
        for url in self.existing_urls:
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield scrapy.Request(
                    url, callback=self.parse_detail, errback=self.handle_error
                )

        # do pagination
        last_page = response.css("ul.pagination li:contains(Last) a::attr(href)").get()
        if last_page:
            max_page = last_page.split("=")[-1]
            max_page = int(max_page)
            for i in range(2, max_page + 1):
                # example: https://ubudproperty.com/listing-villaforsale=2
                next_page = response.url + "=" + str(i)
                footprint = response.url.split("/")[-1].split("=")[0].split("-")[-1]
                footprint += "=" + str(i)
                if footprint not in self.visited_urls:
                    self.visited_urls.append(footprint)
                    yield scrapy.Request(next_page, callback=self.parse)

    def parse_detail(self, response):
        try:
            loader = ItemLoader(item=PropertyItem(), selector=response)
            # collect raw data
            loader.add_value("source", "Ubud Property")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)
            # pre processed data
            alt_title = (
                response.css("h2.title::Text").get().strip()
            )  # price also exists in here
            idr = find_idr(alt_title)
            usd = find_usd(alt_title)
            ## finding lisiting listed/publish date
            sources = response.css("img[src]::attr(src)").getall()
            publish_dates = list(map(extract_publish_date, sources))
            publish_dates = list(filter(lambda d: d, publish_dates))
            if publish_dates:
                pdate = max(publish_dates)
            else:
                pdate = None
            ## finding leasehold years
            leasehold_years_text = response.css("h5 ::Text").get()
            # template selector
            template_css = "div.table-fut table tr:contains({}) td:last-child::Text"
            # collect property data
            loader.add_value("property_id", alt_title, MapCompose(find_code))
            # loader.add_css('is_off_plan', '')
            if pdate:
                loader.add_value("listed_date", pdate.strftime(r"%Y-%m-%d"))
            loader.add_css(
                "title",
                "div#ENG p span::Text,div#ENG p strong::Text, div#ENG p::Text",
                MapCompose(str.strip),
            )
            loader.add_value("location", "Ubud")
            loader.add_css("contract_type", template_css.format("TITLE"))
            loader.add_css(
                "property_type",
                "div#ENG p span::Text,div#ENG p strong::Text",
                MapCompose(lambda w: w.split(" ")[0].title()),
            )
            loader.add_value(
                "leasehold_years",
                leasehold_years_text,
                MapCompose(find_leasehold_years),
            )
            loader.add_css("bedrooms", template_css.format("BEDROOM"))
            loader.add_css("bathrooms", template_css.format("BATHROOM"))
            loader.add_css(
                "land_size",
                template_css.format("LAND"),
                MapCompose(find_land_size),
            )
            loader.add_css(
                "build_size",
                template_css.format("BUILDING"),
                MapCompose(find_build_size),
            )
            if idr:
                loader.add_value("price", idr)
                loader.add_value("currency", "IDR")
            elif usd:
                loader.add_value("price", usd)
                loader.add_value("currency", "USD")
            loader.add_css("image_url", "div.thumbDetail img::attr(src)")
            loader.add_value("availability_label", "Available")
            loader.add_css("description", "div#ENG ::Text,div.sideDetail table ::Text")
            # redefine value based on collected value
            item = loader.load_item()
            ## replace title with alt_title if not exist
            title = item.get("title", None)
            if not title or title == ".":
                item["title"] = alt_title
            ## define property type
            bedrooms = item.get("bedrooms", 0)
            property_type = item.get("property_type", "")
            if title and property_type not in ["Villa", "Land", "House"]:
                result = re.search(
                    r"(land|hotel|villa)", title, re.IGNORECASE
                )  # find land,hotel,and villa keyword in title
                if result:
                    property_type = result.group().title()
                    property_type = define_property_type(property_type)
                    item["property_type"] = property_type
                else:
                    item["property_type"] = "Villa" if bedrooms > 0 else "Land"
            ## remove title text from the description
            desc = item.get("description", "")
            if item.get("title", "") in desc:
                item["description"] = desc.replace(title, "")
            ## find leasehold years in the table ##
            contract_type = item.get("contract_type")
            leasehold_years = item.get("leasehold_years")
            alt_years = response.css(
                "table tr:contains(LEASING) td:last-child ::Text"
            ).get()
            if "Leasehold" in contract_type and not leasehold_years and alt_years:
                item["leasehold_years"] = find_leasehold_years(alt_years)
            ## make sure the leasehold_years is empty on freehold ##
            if "Freehold" in contract_type:
                item["leasehold_years"] = None
            yield item
        except Exception as err:
            error = Error(
                url=response.url,
                source="Spider",
                error_message=str(err),
            )
            # Capture the traceback and add it to the error message
            tb = traceback.format_exc()
            error.error_message += f"\nTraceback:\n{tb}"
            db = next(get_db())
            db.add(error)
            db.commit()
