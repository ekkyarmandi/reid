import traceback
import re
from models.error import Error
from reid.database import get_db
from itemloaders.processors import MapCompose
from reid.spiders.base import BaseSpider
from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from reid.func import (
    extract,
    find_contract_type,
    find_lease_years,
    find_published_date,
    are_to_sqm,
    dimension_remover,
    identify_currency,
    define_property_type,
)


class PropertiaBaliSpider(BaseSpider):
    name = "propertiabali"
    allowed_domains = ["propertiabali.com", "propertia.com"]
    start_urls = ["https://propertiabali.com/bali-villas-for-sale"]

    def parse(self, response):
        # get properties urls
        urls = response.css("#module_properties a[target]::attr(href)").getall()
        urls = list(dict.fromkeys(urls))

        # loop and parse it to parse_detail
        for url in urls:
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(
                    url=url,
                    callback=self.parse_detail,
                    errback=self.handle_error,
                )

        # loop and parse it to parse_detail
        for url in self.existing_urls:
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(
                    url=url,
                    callback=self.parse_detail,
                    errback=self.handle_error,
                )

        # get the next page url
        next_url = response.css(
            "ul.pagination li > a[aria-label=Next]::attr(href)"
        ).get()
        next_url = response.urljoin(next_url)
        if next_url and "http" in next_url:
            yield response.follow(url=next_url, callback=self.parse)

    def parse_detail(self, response):
        try:
            loader = ItemLoader(item=PropertyItem(), selector=response)
            loader.add_value("source", "Propertia")
            loader.add_value("url", response.url)
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("html", response.text)

            labels = response.css(
                "div.wpl_prp_gallery div.wpl-listing-tags-cnt div.wpl-listing-tag::text"
            ).getall()
            labels.append("Available")

            loader.add_css(
                "title",
                "h1::text",
            )
            loader.add_css(
                "listed_date",
                "script[type='application/ld+json']",
                MapCompose(find_published_date),
            )
            loader.add_css(
                "property_id",
                "div.detail-wrap > ul > li:contains('Property ID') span::Text",
            )
            loader.add_css(
                "location",
                "div.detail-wrap > ul > li:contains('Area') span::Text",
            )
            loader.add_css(
                "leasehold_years",
                "ul.fave_number-of-years ::Text",
            )
            loader.add_css(
                "contract_type",
                "div.detail-wrap > ul > li:contains('Property Type') span::Text",
                MapCompose(find_contract_type),
            )
            loader.add_css(
                "property_type",
                "div.detail-wrap > ul > li:contains('Property Type') span::Text",
                MapCompose(define_property_type),
            )
            loader.add_css(
                "bedrooms",
                "div.detail-wrap > ul > li:contains('Bedroom') span::Text",
            )
            loader.add_css(
                "bathrooms",
                "div.detail-wrap > ul > li:contains('Bathroom') span::Text",
            )
            loader.add_css(
                "land_size",
                "div.detail-wrap > ul > li:contains('Land Size') span::Text",
                MapCompose(are_to_sqm),
            )
            loader.add_css(
                "build_size",
                "div.detail-wrap > ul > li:contains('Building Size') span::Text",
                MapCompose(
                    lambda u: re.sub(r",", ".", u),
                    are_to_sqm,
                ),
            )
            loader.add_css(
                "price",
                "div.detail-wrap > ul > li:contains('Price') span::Text",
            )
            loader.add_css(
                "currency",
                "div.detail-wrap > ul > li:contains('Price') span::Text",
                MapCompose(identify_currency),
            )
            loader.add_css(
                "image_url",
                "div.property-banner img::attr(src)",
                MapCompose(dimension_remover),
            )
            loader.add_value("availability_label", labels)
            loader.add_css(
                "description",
                "#property-description-wrap div.block-content-wrap p ::Text,#property-description-container::Text",
            )
            loader.add_css(
                "longitude",
                "script#houzez-single-property-map-js-extra::text",
                MapCompose(lambda x: extract(r'"lng"\s*:\s*"(-?[\d.]+)"', x)),
            )
            loader.add_css(
                "latitude",
                "script#houzez-single-property-map-js-extra::text",
                MapCompose(lambda x: extract(r'"lat"\s*:\s*"(-?[\d.]+)"', x)),
            )

            item = loader.load_item()

            leasehold_years = item.get("leasehold_years", None)
            is_leasehold = re.search(
                r"lease",
                item.get("contract_type", ""),
                re.IGNORECASE,
            )
            desc = item.get("description", "")
            if is_leasehold and not leasehold_years:
                item["leasehold_years"] = find_lease_years(desc)

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
