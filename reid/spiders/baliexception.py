import scrapy
from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from itemloaders.processors import MapCompose
import re
from reid.spiders.base import BaseSpider
from reid.func import (
    define_property_type,
    extract,
    find_bedrooms,
    find_location_in_title,
    identify_currency,
)
from models.error import Error
from reid.database import get_db
import traceback

import jmespath
import time


class BaliExceptionSpider(BaseSpider):
    name = "baliexception"
    allowed_domains = ["baliexception.com"]

    def start_requests(self):
        self.timestamp = 0
        self.page = 1
        self.max_page = 0
        self.start_url = "https://baliexception.com/buy/"
        self.headers = {
            "cache-control": "no-cache",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "cookies": "wp-wpml_current_language=en",
        }
        # Do initial request
        url = "https://baliexception.com"
        yield scrapy.Request(url, headers=self.headers, callback=self.next_parse)

    def next_parse(self, response):
        # get page_id from the response
        script_text = response.css("script#fp_data_js::Text").get()
        page_id = re.search(r"\"page_id\"\s*:\s*(\d+),", script_text)
        try:
            page_id = page_id.group(1)
        except:
            raise Exception("Page ID is empty")
        #
        payload = f"action=jet_engine_ajax&handler=get_listing&page_settings%5Bpost_id%5D={page_id}&page_settings%5Bqueried_id%5D={page_id}%7CWP_Post&page_settings%5Belement_id%5D=ikgmes&page_settings%5Bpage%5D=1&listing_type=bricks"
        url = self.start_url + f"?nocache={int(time.time())}"
        yield scrapy.Request(
            url=url,
            method="POST",
            headers=self.headers,
            body=payload,
            callback=self.parse,
        )

    def parse(self, response):
        result = response.json()
        response = scrapy.Selector(text=result["data"]["html"])

        # find the property urls
        urls = response.css("div[data-post-id] a[href!='#']::attr(href)").getall()
        urls = list(dict.fromkeys(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_detail)

        # go to the next page
        if self.max_page == 0:
            self.max_page = jmespath.search(
                "data.filters_data.props.default.max_num_pages", result
            )
            listing_id = jmespath.search(
                "data.filters_data.settings.default.lisitng_id", result
            )
            for page in range(2, self.max_page + 1):
                prev_page = page - 1
                headers = {
                    "cache-control": "no-cache",
                    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                }
                payload = f"action=jet_smart_filters&provider=jet-engine%2Fdefault&defaults%5Bpost_status%5D%5B%5D=publish&defaults%5Bpost_type%5D%5B%5D=property&defaults%5Bposts_per_page%5D=10&defaults%5Bpaged%5D=1&defaults%5Bignore_sticky_posts%5D=1&settings%5Blisitng_id%5D={listing_id}&settings%5Bcolumns%5D=2&settings%5Bcolumns_tablet%5D=3&settings%5Bcolumns_mobile%5D=1&settings%5Bcolumn_min_width%5D=240&settings%5Bcolumn_min_width_tablet%5D=240&settings%5Bcolumn_min_width_mobile%5D=240&settings%5Binline_columns_css%5D=false&settings%5Bpost_status%5D%5B%5D=publish&settings%5Buse_random_posts_num%5D=false&settings%5Bposts_num%5D=10&settings%5Bmax_posts_num%5D=9&settings%5Bnot_found_message%5D=No%2Bdata%2Bwas%2Bfound&settings%5Bis_masonry%5D=false&settings%5Bequal_columns_height%5D=false&=settings%5Buse_load_more%5D%3D&=settings%5Bload_more_id%5D%3D&=settings%5Bloader_text%5D%3D&=settings%5Binject_alternative_items%5D%3D&=settings%5B_element_id%5D%3D&=settings%5Bjet_rest_query%5D%3D&settings%5Bload_more_type%5D=click&settings%5Bloader_spinner%5D=false&settings%5Buse_custom_post_types%5D=true&settings%5Bcustom_post_types%5D%5B%5D=property&settings%5Bhide_widget_if%5D=always_show&settings%5Bcarousel_enabled%5D=false&settings%5Bslides_to_scroll%5D=1&settings%5Barrows%5D=true&settings%5Barrow_icon%5D=fa%2Bfa-angle-left&settings%5Bdots%5D=false&settings%5Bautoplay%5D=true&settings%5Bpause_on_hover%5D=true&settings%5Bautoplay_speed%5D=5000&settings%5Binfinite%5D=true&settings%5Bcenter_mode%5D=false&settings%5Beffect%5D=slide&settings%5Bspeed%5D=500&settings%5Bscroll_slider_enabled%5D=false&settings%5Bscroll_slider_on%5D%5B%5D=desktop&settings%5Bscroll_slider_on%5D%5B%5D=tablet&settings%5Bscroll_slider_on%5D%5B%5D=mobile&settings%5Bcustom_query%5D=false&props%5Bfound_posts%5D=554&props%5Bmax_num_pages%5D={self.max_page}&props%5Bpage%5D={prev_page}&paged={page}"
                url = "https://baliexception.com/wp-admin/admin-ajax.php"
                yield scrapy.Request(
                    url=url,
                    method="POST",
                    headers=headers,
                    body=payload,
                    callback=self.parse_next_page,
                )

    def parse_next_page(self, response):
        data = response.json()
        response = scrapy.Selector(text=data.get("content", "<html>empty</html>"))
        # find property urls
        urls = response.css("div[data-post-id] a[href!='#']::attr(href)").getall()
        urls = list(dict.fromkeys(urls))
        for url in urls:
            yield scrapy.Request(url, callback=self.parse_detail)

    def parse_detail(self, response):
        try:
            ## lambda functions
            get_first = lambda text, sep: str(text).split(sep)[0]
            get_last = lambda text, sep: str(text).split(sep)[-1]
            ## main logic
            loader = ItemLoader(item=PropertyItem(), selector=response)
            loader.add_value("source", "Bali Exception")
            loader.add_value("scraped_at", self.scraped_at)
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)
            ## main extraction function
            detail_selector = "section div.detailProperty:contains('{}') > div::Text"
            loader.add_css("title", "h1::text")
            loader.add_css("property_id", detail_selector.format("Property ID"))
            loader.add_css(
                "leasehold_years",
                detail_selector.format("Leasehold"),
                MapCompose(
                    lambda value: get_first(value, "+"),
                    lambda value: value.replace(",", "."),
                ),
            )
            loader.add_css(
                "bedrooms",
                "ul.featureList li:contains(Bedroom) span:last-child::Text",
                MapCompose(
                    lambda value: get_last(value, "–"),
                    lambda value: get_last(value, "-"),
                    lambda value: get_last(value, "/"),
                    lambda value: get_first(value, "+"),
                    lambda value: value.replace(",", "."),
                ),
            )
            loader.add_css(
                "bathrooms",
                "ul.featureList li:contains(Bathroom) span:last-child::Text",
                MapCompose(
                    lambda value: get_last(value, "/"),
                    lambda value: value.replace(",", "."),
                ),
            )
            loader.add_css(
                "land_size",
                detail_selector.format("Land size"),
                MapCompose(
                    lambda value: get_last(value, "–"),
                    lambda value: get_last(value, "-"),
                    lambda value: get_first(value, "+"),
                    lambda value: get_last(value, "/"),
                    lambda value: value.replace(",", "."),
                ),
            )
            loader.add_css(
                "build_size",
                detail_selector.format("Building size"),
                MapCompose(
                    lambda value: get_last(value, "–"),
                    lambda value: get_last(value, "-"),
                    lambda value: get_first(value, "+"),
                    lambda value: get_last(value, "/"),
                    lambda value: value.replace(",", "."),
                ),
            )
            loader.add_css("location", "ol.breadcrumb > li a[itemid*=area] span::Text")
            loader.add_css("price", "p.converted-price::Text")
            loader.add_css(
                "currency",
                "p.converted-price::Text",
                MapCompose(identify_currency),
            )
            loader.add_css("image_url", "figure img::attr(src)")
            loader.add_css("description", "div[class*=post-content] ::Text")
            loader.add_value("availability_label", "Available")

            # property type and contract type
            title = response.css("h1::text").get()
            contract_type = "Freehold"  # default contract type
            result = re.search(r"freehold|leasehold", title.lower())
            if result:
                a, b = result.start(), result.end()
                contract_type = title[a:b].title()
            loader.add_value("contract_type", contract_type)

            property_type = response.css(
                "ul.featureList li:contains(Type) span.meta a::Text"
            ).get()
            if not property_type:
                property_type = define_property_type(title)
            loader.add_value("property_type", property_type)

            # location fallback
            location = response.css(
                "ol.breadcrumb > li a[itemid*=area] span::Text"
            ).get()
            if not location:
                splits = title.split("|")
                if len(splits) > 1:
                    loader.add_value("location", splits[1].strip())
                else:
                    loader.add_value("location", find_location_in_title(title))

            # bedrooms fallback
            bedrooms = response.css(
                "ul.featureList li:contains(Bedroom) span:last-child::Text"
            ).get()
            if not bedrooms:
                value = find_bedrooms(title.lower())
                loader.add_value("bedrooms", value)
                loader.add_value("bathrooms", value)

            # response.css("script:contains(lng)::text").re_first(r"lng\s*=\s*(-?[\d.]+)")
            loader.add_css(
                "longitude",
                "script:contains(lng)::text",
                MapCompose(lambda x: extract(r"lng\s*=\s*(-?[\d.]+)", x)),
            )
            loader.add_css(
                "latitude",
                "script:contains(lat)::text",
                MapCompose(lambda x: extract(r"lat\s*=\s*(-?[\d.]+)", x)),
            )
            item = loader.load_item()
            yield item

        except Exception as err:
            error = Error(
                url=response.url,
                source="BaliExceptionSpider",
                error_message=str(err),
            )
            # Capture the traceback and add it to the error message
            tb = traceback.format_exc()
            error.error_message += f"\nTraceback:\n{tb}"
            db = next(get_db())
            db.add(error)
            db.commit()
