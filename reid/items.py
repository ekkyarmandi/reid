# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from itemloaders.processors import TakeFirst, MapCompose

from reid.func import (
    AnySoldDelisted,
    JoinAndStrip,
    extract_currency,
    standardize_property_type,
    to_number,
)


class PropertyItem(scrapy.Item):
    # raw data
    source = scrapy.Field(output_processor=TakeFirst())
    url = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=TakeFirst(),
    )
    html = scrapy.Field(output_processor=TakeFirst())
    json = scrapy.Field(output_processor=TakeFirst())
    # property data
    property_id = scrapy.Field(output_processor=TakeFirst())
    scraped_at = scrapy.Field(output_processor=TakeFirst())
    listed_date = scrapy.Field(
        input_processor=MapCompose(str.strip), output_processor=TakeFirst()
    )
    title = scrapy.Field(
        input_processor=MapCompose(str.strip), output_processor=TakeFirst()
    )
    location = scrapy.Field(
        input_processor=MapCompose(str.strip), output_processor=TakeFirst()
    )
    contract_type = scrapy.Field(
        input_processor=MapCompose(str.strip), output_processor=TakeFirst()
    )
    property_type = scrapy.Field(
        input_processor=MapCompose(str.strip, standardize_property_type),
        output_processor=TakeFirst(),
    )
    leasehold_years = scrapy.Field(
        input_processor=MapCompose(to_number), output_processor=TakeFirst()
    )
    bedrooms = scrapy.Field(
        input_processor=MapCompose(to_number), output_processor=TakeFirst()
    )
    bathrooms = scrapy.Field(
        input_processor=MapCompose(to_number), output_processor=TakeFirst()
    )
    land_size = scrapy.Field(
        input_processor=MapCompose(to_number), output_processor=TakeFirst()
    )
    build_size = scrapy.Field(
        input_processor=MapCompose(to_number), output_processor=TakeFirst()
    )
    price = scrapy.Field(
        input_processor=MapCompose(to_number), output_processor=TakeFirst()
    )
    currency = scrapy.Field(
        input_processor=MapCompose(str.strip, str.upper),
        output_processor=TakeFirst(),
    )
    image_url = scrapy.Field(
        input_processor=MapCompose(str.strip), output_processor=TakeFirst()
    )
    availability_label = scrapy.Field(
        input_processor=MapCompose(str.strip), output_processor=AnySoldDelisted()
    )
    sold_at = scrapy.Field(output_processor=TakeFirst())
    description = scrapy.Field(
        input_processor=MapCompose(str.strip), output_processor=JoinAndStrip("\n")
    )
    is_off_plan = scrapy.Field(
        input_processor=MapCompose(str.strip), output_processor=TakeFirst()
    )
    ## New fields
    longitude = scrapy.Field(
        input_processor=MapCompose(float), output_processor=TakeFirst()
    )
    latitude = scrapy.Field(
        input_processor=MapCompose(float), output_processor=TakeFirst()
    )
