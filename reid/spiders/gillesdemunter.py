from reid.spiders.base import BaseSpider
from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from itemloaders.processors import MapCompose
from reid.func import (
    define_property_type,
    delisted_item,
    extract,
)


class GillesdemunterSpider(BaseSpider):
    name = "gillesdemunter"
    allowed_domains = ["gillesdemunter.com"]
    start_urls = [
        f"https://www.gillesdemunter.com/properties.sale.list.php?search=search&p={p}"
        for p in range(1, 29)
    ]

    def parse(self, response):
        items = response.css(".container-fluid div.container div.item:has(h2.desktop)")
        for item in items:
            url = item.css("a::attr(href)").get()
            url = response.urljoin(url)
            is_private = item.css(".container-caption h3::text").get()
            if not is_private:
                yield response.follow(url, callback=self.parse_detail)

    def parse_detail(self, response):
        loader = ItemLoader(item=PropertyItem(), selector=response)
        loader.add_value("source", "GD&ASSOCIATES")
        loader.add_value("scraped_at", self.scraped_at)
        loader.add_value("url", response.url)
        loader.add_value("html", response.text)

        headers = response.css(
            "div.price:first-child div:nth-child(1) div.title::text"
        ).getall()

        values = response.css(
            (
                "div.price:first-child div:nth-child(2) span.text::Text,"
                "div.price:first-child div:nth-child(2) span.value::Text,"
                "div.price:first-child div:nth-child(2) span::Text"
            )
        ).getall()

        # d = {k: v for k, v in zip(headers, values)}

        bedrooms = response.css(
            ".container div.col-4:contains(BED) span:last-child::text"
        ).get()
        if not bedrooms:
            yield delisted_item
        bed, bath = bedrooms.split("/")
        loader.add_css("title", "h1::text")
        loader.add_css("location", "h2::text")
        loader.add_css("image_url", "img[src*=listing]::attr(src)")
        loader.add_css(
            "land_size",
            "div.land div.col-4:contains(LAND) span:last-child::text",
        )
        loader.add_css(
            "build_size",
            "div.land div.col-4:contains(LIVING) span:last-child::text",
        )
        loader.add_value("bedrooms", bed)
        loader.add_value("bathrooms", bath)
        loader.add_css("contract_type", "div.price span:contains(hold)::text")
        loader.add_css(
            "property_type",
            "h1::text",
            MapCompose(str.strip, define_property_type),
        )
        loader.add_css(
            "leasehold_years",
            "div.row:contains(Leasehold) div.col-4:contains(years) span::text",
        )
        loader.add_css("price", "div.price span:contains(USD) + span::text")
        loader.add_value("currency", "USD")
        loader.add_value("availability_label", "Available")
        loader.add_css("description", "div[class*=col] p.font3.f12::text")

        # response.css("script:contains(lng)::text").re_first(r'lng\s*:\s*(-?[\d.]+)')
        loader.add_css(
            "longitude",
            "script:contains(lng)::text",
            MapCompose(lambda x: extract(r"lng\s*:\s*(-?[\d.]+)", x)),
        )
        loader.add_css(
            "latitude",
            "script:contains(lat)::text",
            MapCompose(lambda x: extract(r"lat\s*:\s*(-?[\d.]+)", x)),
        )

        item = loader.load_item()

        item["property_id"] = item["image_url"].split("/")[3]

        yield item
