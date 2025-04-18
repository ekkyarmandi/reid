from itemloaders import ItemLoader
from itemloaders.processors import MapCompose
from scrapy.http import TextResponse
from reid.func import (
    define_property_type,
    dimension_remover,
    find_published_date,
    get_lease_years,
)
from reid.items import PropertyItem
from reid.spiders.base import BaseSpider
from reid.database import get_db
from models.error import Error
import traceback
import re


class TealestateSpider(BaseSpider):
    name = "tealestate"
    allowed_domains = ["tealestate.co"]
    start_urls = [
        "https://tealestate.co/wp-admin/admin-ajax.php?action=jet_smart_filters&provider=jet-engine%2fdefault&defaults%5bpost_status%5d%5b%5d=publish&defaults%5bpost_type%5d=properties&defaults%5bposts_per_page%5d=10&defaults%5bpaged%5d=1&defaults%5bignore_sticky_posts%5d=1&defaults%5borderby%5d%5bsold%5d=asc&defaults%5borderby%5d%5bdate%5d=desc&defaults%5bmeta_key%5d=sold&settings%5blisitng_id%5d=412&settings%5bcolumns%5d=2&settings%5bcolumns_tablet%5d=2&settings%5bcolumns_mobile%5d=1&settings%5bpost_status%5d%5b%5d=publish&settings%5bposts_num%5d=10&settings%5bmax_posts_num%5d=9&settings%5bnot_found_message%5d=no%2bproperty%2bmatch%2byour%2bcriteria&settings%5bequal_columns_height%5d=yes&settings%5bload_more_type%5d=click&settings%5bslides_to_scroll%5d=1&settings%5barrows%5d=true&settings%5barrow_icon%5d=fa%2bfa-angle-left&settings%5bautoplay%5d=true&settings%5bautoplay_speed%5d=5000&settings%5binfinite%5d=true&settings%5beffect%5d=slide&settings%5bspeed%5d=500&settings%5binject_alternative_items%5d&settings%5bscroll_slider_enabled%5d&settings%5bscroll_slider_on%5d%5b%5d=desktop&settings%5bscroll_slider_on%5d%5b%5d=tablet&settings%5bscroll_slider_on%5d%5b%5d=mobile&props%5bfound_posts%5d=472&props%5bmax_num_pages%5d=48&props%5bpage%5d=1&paged=1"
    ]

    def parse(self, response):
        try:
            data = response.json()
        except:
            data = {}
        content = data.get("content", "")
        content = TextResponse(url=response.url, body=content, encoding="utf-8")
        items = content.css(".jet-listing-grid__item")
        for item in items:
            _id = item.css(
                "div.jet-listing-dynamic-field__content:contains(TE)::text"
            ).get()
            url = response.urljoin("/properties/" + _id.lower() + "/")
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(url, callback=self.parse_detail)
        # fetch existing urls
        existing_urls = [
            url for url in self.existing_urls if url not in self.visited_urls
        ]
        for url in existing_urls:
            if url not in self.visited_urls:
                self.visited_urls.append(url)
                yield response.follow(url, callback=self.parse_detail)
        # go to next url
        pagination = data.get("pagination")
        if pagination:
            prev_page = re.search(r"paged=(?P<page>\d+)", response.url).group("page")
            prev_page = int(prev_page)
            max_page = pagination.get("max_num_pages")
            if int(prev_page) <= max_page:
                next_url = response.url.replace(
                    f"paged={prev_page}", f"paged={prev_page+1}"
                )
                yield response.follow(next_url, callback=self.parse)

    def parse_detail(self, response):
        try:
            ## lambda functions
            get_first = lambda text, sep: str(text).split(sep)[0]
            get_last = lambda text, sep: str(text).split(sep)[-1]
            ## extractions main logic
            loader = ItemLoader(item=PropertyItem(), selector=response)
            loader.add_value("source", "Teal Estate")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)

            labels = response.css(
                ".elementor-widget-wrap.elementor-element-populated:has(.elementor-background-overlay) [role='button'] ::text"
            ).getall()

            if len(labels) == 0:
                labels = ["Available"]

            loader.add_css("title", "h3.elementor-heading-title::text")
            loader.add_css(
                "listed_date",
                "script[type='application/ld+json']::text",
                MapCompose(find_published_date),
            )
            loader.add_css(
                "property_id",
                "div.jet-listing-dynamic-field__content:contains(TE)::text",
            )
            loader.add_css(
                "location",
                "h3.elementor-icon-box-title:contains(Location) + p::text",
            )
            loader.add_css(
                "leasehold_years",
                "div.elementor-widget-heading:contains(hold) + div div.jet-listing-dynamic-field__content::text",
                MapCompose(get_lease_years),
            )
            loader.add_css(
                "contract_type",
                "div.elementor-heading-title:contains(hold)::text",
            )
            loader.add_css(
                "bedrooms",
                [
                    "div.jet-listing-dynamic-field__content:contains(Bed)::text",
                    "h3:contains(Bed) + p::text",
                ],
            )
            loader.add_css(
                "bathrooms",
                [
                    "div.jet-listing-dynamic-field__content:contains(Bath)::text",
                    "h3:contains(Bath) + p::text",
                ],
            )
            loader.add_css(
                "land_size",
                "h3.elementor-icon-box-title:contains('Land Size') + p::text",
                MapCompose(
                    lambda value: value.replace(",", "."),
                    lambda value: get_last(value, "-"),
                ),
            )
            loader.add_css(
                "build_size",
                "h3.elementor-icon-box-title:contains('Building Size') + p::text",
                MapCompose(
                    lambda value: value.replace(",", "."),
                    lambda value: get_last(value, "-"),
                ),
            )
            loader.add_css(
                "price",
                "div.jet-listing-dynamic-field__content:contains(IDR)::text",
            )
            loader.add_value("currency", "IDR")
            loader.add_css(
                "image_url",
                "div[data-widget_type='image.default'] img[src]::attr(src)",
                MapCompose(dimension_remover),
            )
            loader.add_value(
                "availability_label",
                labels,
            )
            loader.add_css(
                "description",
                "div:contains(Description) + div p ::text",
            )
            loader.add_css(
                "property_type",
                "h3.elementor-heading-title::text",
                MapCompose(define_property_type),
            )

            item = loader.load_item()

            contract_type = item.get("contract_type")
            if not contract_type:
                item["availability_label"] = "Delisted"

            yield item
        except Exception as e:
            error = Error(
                url=response.url,
                source="Spider",
                error_message=str(e),
            )
            # Capture the traceback and add it to the error message
            tb = traceback.format_exc()
            error.error_message += f"\nTraceback:\n{tb}"
            db = next(get_db())
            db.add(error)
            db.commit()
            db.close()
