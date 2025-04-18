import scrapy
from scrapy.loader import ItemLoader
from reid.items import PropertyItem
from itemloaders.processors import MapCompose
from reid.database import get_db
from models.error import Error
import jmespath
import json
import re
import traceback
from reid.spiders.base import BaseSpider
from reid.func import (
    define_property_type,
    extract,
    find_build_size,
    find_lease_years,
    get_icons,
)
from urllib.parse import urlencode


class BaliTreasurePropertiesSpider(BaseSpider):
    name = "balitreasureproperties"
    allowed_domains = ["balitreasureproperties.com", "q42ljy6v.apicdn.sanity.io"]
    current_page = 1

    def start_requests(self):
        offset = 50
        for i in range(0, 7):
            querystring = {
                "query": "{\n    'cards': *[_type == 'villaSale' && (coalesce(property->listingStatus, listingStatus) == 'available' || coalesce(property->visibility, visibility) == 'online') && visibility == 'public' && select(_type == 'villaSale' => !(true in categories[]->hideFromSearch), true)] {\n      \n    \n  _id,\n  _createdAt,\n  'slug': slug.current,\n  visibility,\n  title,\n  'listingType': _type,\n  'defaultListing': select(_type == 'villaRental' => coalesce(yearlyRental._type, monthlyRental._type), coalesce(leaseholdSale._type, freeholdSale._type)), \n  tags,\n  description,\n  'image': coalesce(thumbnailImage, featuredImage, property->featuredImage) {..., asset->},\n  'property': select(_type == 'landSale' => @, property->) {\n    // ...,\n    featuredImage {..., asset->},\n    'label': select(listingStatus == 'soldByBtp' => 'soldByBtp', listingType == 'exclusive' => 'btpExclusive', null),\n    area->{\n      name,\n      'slug': slug.current,\n      _type,\n      'subarea': ^.subArea-> {\n        name,\n        'slug': slug.current,\n        _type,\n      }\n    },\n    name,\n    'slug': slug.current,\n    'codeName': codeName.current,\n    floorPlans [] {..., asset->},\n    landSize,\n    landTitle,\n    excerpt,\n    'gallery': select(\n      gallerySource == 'tag' => *[_type=='sanity.imageAsset' && references(^.galleryTag._ref)] | order(originalFilename asc) {\n        '_type': 'image',\n        'asset': @,\n      }, \n      gallery[_type=='image'] {..., asset->},\n    )[0...7],\n    // VILLA\n    buildingSize,\n    buildingYear,\n    details,\n    // LAND\n    zoning,\n    propertyView,\n    buildingPermit,\n    landLayout {..., asset->},\n    location,\n    virtualTour,\n    walkthrough,\n    }\n  ,\n    'listings': [\n      monthlyRental,\n      yearlyRental {\n        ...,\n        'availableOn': ^.availableOn,\n        'availableDate': ^.availableDate,\n      },\n      leaseholdSale,\n      freeholdSale\n    ] [_type in ^.availableFor]\n,\n  } [length(listings) > 0],\n} {\n  cards {\n    ...,\n    'listings': listings[] {\n      ...,\n      'priceUsd': select(price.currency == 'usd' => price.amount, price.amount/$conversion),\n    }\n  }[] | order(coalesce(property.listingDate, listingDate, _createdAt) desc) [$from...$to],\n  'cardsTotal': count(cards),\n}",
                "$listingType": '"villaSale"',
                "$sublisting": "null",
                "$from": str(i * offset),
                "$to": str(i * offset + offset),
                "$conversion": "16283.033777346152",
                "$isDevelopment": "false",
                "$admin": "false",
                "$category": "null",
                "$sort": '"coalesce(property.listingDate, listingDate, _createdAt)"',
                "$sortOrder": '"desc"',
                "$tag": "null",
                "$priceMin": "null",
                "$priceMax": "null",
                "$landSizes": "null",
                "$areas": "null",
                "$subAreas": "null",
                "returnQuery": "false",
            }
            headers = {
                "accept": "application/json",
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            }
            url = (
                "https://q42ljy6v.apicdn.sanity.io/v2024-11-01/data/query/production?"
                + urlencode(querystring)
            )
            yield scrapy.Request(url, headers=headers, callback=self.parse)

    def parse(self, response):
        data = response.json()
        cards = jmespath.search("result.cards", data)
        for card in cards:
            url = (
                "https://www.balitreasureproperties.com/bali-villas-for-sale/listings/leasehold/"
                + card.get("slug")
            )
            yield scrapy.Request(
                url,
                meta={"data": card},
                callback=self.parse_detail,
                errback=self.handle_error,
            )

    def parse_detail(self, response):
        try:
            ## lambda functions ##
            has_leasehold = lambda text: re.search(r"lease", text, re.IGNORECASE)
            get_first = lambda str, separator: str.split(separator)[0]
            get_last = lambda str, separator: str.split(separator)[-1]
            ## main logic ##
            data = response.meta.get("data", {})
            loader = ItemLoader(item=PropertyItem(), selector=response)
            loader.add_value("source", "Bali Treasure Properties")
            loader.add_value("url", response.url)
            loader.add_value("html", response.text)
            loader.add_value("json", json.dumps(data))
            loader.add_value("scraped_at", self.scraped_at)
            # contract_types = response.css(".second_line a[rel*=property_id]::text").getall()
            icons = get_icons(
                response.css(
                    "div.p-property div.le_icons div.facility_icons::attr(title)"
                ).getall()
            )

            # new value
            title = data.get("title")
            property_id = data.get("_id")
            contract_text = data.get("defaultListing")
            property_text = data.get("listingType")
            publish_date = data.get("_createdAt")
            image_url = jmespath.search("image.asset.url", data)

            loader.add_value("price", jmespath.search("listings[0].price.amount", data))
            loader.add_value(
                "currency", jmespath.search("listings[0].price.currency", data)
            )

            leasehold_years = jmespath.search("listings[0].period", data)

            p = jmespath.search("description", data)
            descriptions = [
                jmespath.search(f"description[{x}].children[0].text", data)
                for x in range(len(p))
            ]

            if has_leasehold(contract_text):
                loader.add_value("contract_type", "Leasehold")
                loader.add_value("leasehold_years", leasehold_years)
            else:
                loader.add_value("contract_type", "Freehold")

            # convert date to YYYY-MM-DD
            loader.add_value(
                "listed_date",
                publish_date,
                MapCompose(lambda date: date.split("T")[0]),
            )

            # find location
            city = jmespath.search("property.area.name", data)
            subarea = jmespath.search("property.area.subarea.name", data)
            loader.add_value("location", f"{subarea}, {city}")

            loader.add_css("location", "div.p-property h1 + span.area strong::text")
            loader.add_value("property_id", property_id)
            loader.add_value("title", title)
            loader.add_css(
                "bedrooms",
                "div[class*=card_facts] div:contains(Bedroom) p:first-child::Text",
            )
            loader.add_css(
                "bathrooms",
                "div[class*=card_facts] div:contains(Bathroom) p:first-child::Text",
            )
            loader.add_css(
                "land_size",
                "div[class*=card_facts] div:contains(Land) p:first-child span::Text",
            )
            loader.add_css(
                "build_size",
                "div[class*=card_facts] div:contains(Building) p:first-child span::Text",
            )
            loader.add_value("image_url", image_url)
            loader.add_css(
                "availability_label", "div.second_line div.availability strong::text"
            )
            loader.add_value("description", descriptions)
            loader.add_value("availability_label", "Available")
            # response.css("script:contains(locationCoordinates)").re_first(r'\"locationCoordinates\\"\s*:\s*\\"(.*?)\\"')
            # output: -8.8169211, 115.1156331
            loader.add_css(
                "longitude",
                "script:contains(locationCoordinates)::text",
                MapCompose(
                    lambda x: extract(
                        r'locationCoordinates\s*\\":\s*\\".*?,\s*(.*?)\\"', x
                    )
                ),
            )
            loader.add_css(
                "latitude",
                "script:contains(locationCoordinates)::text",
                MapCompose(
                    lambda x: extract(r'locationCoordinates\s*\\":\s*\\"(.*?),', x)
                ),
            )

            item = loader.load_item()

            title = item.get("title")
            contract_type = item.get("contract_type")
            if title and contract_type:
                item["contract_type"] += " " + define_property_type(property_text)
            else:
                item["title"] = "N/A"
                item["availability_label"] = "Delisted"

            if not item.get("leasehold_years"):
                item["leasehold_years"] = find_lease_years(item.get("description", ""))

            self.labels = loader.selector.css(
                "div.second_line div.availability strong::text"
            ).getall()
            self.labels = list(
                filter(lambda str: str != "", map(str.strip, self.labels))
            )

            # get the building size from description
            description = item.get("description", "")
            build_size = item.get("build_size", None)
            if description != "" and not build_size:
                item["build_size"] = find_build_size(description)
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
