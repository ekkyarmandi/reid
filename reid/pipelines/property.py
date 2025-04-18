from models.duplicate_listing import DuplicateListing
from models.listing import Listing
from reid.database import get_db
from models.property import Property
from models.rawdata import RawData
from models.error import Error
from models.report import Report
from scrapy.exceptions import DropItem
from datetime import datetime as dt
import logging


class RawDataPipeline:
    def __init__(self):
        self.source = None

    def process_item(self, item, spider):
        self.source = item["source"]
        if item.get("skip", False):
            return item
        # store raw data
        db = next(get_db())
        raw_data_item = dict(
            url=item["url"],
            html=item.get("html", ""),
            json=item.get("json", ""),
        )
        raw_data = RawData(**raw_data_item)
        db.add(raw_data)
        db.commit()
        item = dict(item)
        item["raw_data_id"] = raw_data.id
        return item

    def open_spider(self, spider):
        # load existing and still available listing urls
        db = next(get_db())
        source_name = spider.name
        listings = (
            db.query(Listing)
            .filter(
                Listing.is_available == True,
                Listing.is_excluded == False,
                Listing.excluded_by == None,
                Listing.url.like(f"%{source_name}%"),
            )
            .all()
        )
        spider.existing_urls = [listing.url for listing in listings]

    def close_spider(self, spider):
        # get spider stats
        stats = spider.crawler.stats.get_stats()
        # create spider report
        start_time = stats.get("start_time", 0)
        elapsed_time = dt.now(start_time.tzinfo) - start_time
        spider_stats = dict(
            source=self.source,
            scraped_at=spider.scraped_at,
            item_scraped_count=stats.get("item_scraped_count", 0),
            item_dropped_count=stats.get("item_dropped_count", 0),
            response_error_count=stats.get("log_count/ERROR", 0),
            elapsed_time_seconds=elapsed_time.total_seconds(),
        )
        report = Report(**spider_stats)
        db = next(get_db())
        db.add(report)
        db.commit()


class PropertyPipeline:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        handler = logging.FileHandler("dropped_items.log")
        self.logger.addHandler(handler)

    def process_item(self, item, spider):
        if item.get("skip", False):
            return item
        # remove unnecessary fields after raw data
        item.pop("html", None)
        item.pop("json", None)
        # modify item to match property model
        if item.get("availability_label"):
            item["availability"] = item.pop("availability_label")
            item["is_available"] = item["availability"] == "Available"

        try:
            db = next(get_db())
            property = Property(**item)
            property.check_off_plan()
            property.define_land_zoning()  # this will applied to Land property type only
            db.add(property)
            db.commit()
            db.refresh(property)
            property.identify_issues()
            item["land_zoning"] = property.land_zoning
            # remove errors related to url in spider source
            db.query(Error).filter(
                Error.url == property.url, Error.source == "Spider"
            ).delete()
            db.commit()
        except Exception as e:
            db.rollback()
            # record error
            error = Error(
                url=item.get("url"),
                source="PropertyPipeline",
                error_message=str(e),
            )
            db.add(error)
            db.commit()
            # delete raw data
            raw_data_id = item.get("raw_data_id", None)
            if raw_data_id:
                raw_data = db.query(RawData).filter(RawData.id == raw_data_id).first()
                if raw_data:
                    db.delete(raw_data)
                    db.commit()
            # drop the item
            error_message = f"Error on PropertyPipeline insertion: {e}"
            self.logger.error(error_message)
            raise DropItem(error_message)
        item.pop("id", None)
        return item


class ListingPipeline:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        handler = logging.FileHandler("dropped_items.log")
        self.logger.addHandler(handler)

    def process_item(self, item, spider):
        if item.get("skip", False):
            return item
        # remove raw_data_id
        item.pop("raw_data_id", None)
        # add listing to db
        db = next(get_db())
        listing = Listing(**item)
        listing.classify_tab()
        listing.reid_id_generator(db)
        if listing.reid_id:
            try:
                db.add(listing)
                db.commit()
                # remove error related to the listing if exists
                db.query(Error).filter(Error.url == item.get("url")).delete()
                db.commit()
                # check duplication
                self.__check_duplicate(listing)
            except Exception as e:
                db.rollback()
        else:
            # on constraint conflict do update
            url = item.get("url", "")
            item["updated_at"] = dt.now()
            existing_listing = db.query(Listing).filter(Listing.url == url).first()
            any_changes = existing_listing.compare(item)
            if any_changes:
                existing_listing.classify_tab()
                db.commit()
        return item

    def __check_duplicate(self, listing):
        # check if listing is duplicated from other sources
        db = next(get_db())
        similar_listing = (
            db.query(Listing)
            .filter(
                Listing.price == listing.price,
                Listing.contract_type == listing.contract_type,
                Listing.bedrooms == listing.bedrooms,
                Listing.bathrooms == listing.bathrooms,
                Listing.land_size == listing.land_size,
                Listing.build_size == listing.build_size,
                Listing.source != listing.source,
            )
            .first()
        )
        if similar_listing:
            duplicate_listing = DuplicateListing(
                source_url=similar_listing.url,
                duplicate_url=listing.url,
            )
            try:
                db.add(duplicate_listing)
                db.commit()
            except Exception as e:
                db.rollback()
        # check if listing is duplicated from same source
        similar_listing = (
            db.query(Listing)
            .filter(
                Listing.price == listing.price,
                Listing.contract_type == listing.contract_type,
                Listing.bedrooms == listing.bedrooms,
                Listing.bathrooms == listing.bathrooms,
                Listing.land_size == listing.land_size,
                Listing.build_size == listing.build_size,
                Listing.source == listing.source,
                Listing.url != listing.url,
            )
            .first()
        )
        if similar_listing:
            duplicate_listing = DuplicateListing(
                source_url=similar_listing.url,
                duplicate_url=listing.url,
            )
            try:
                db.add(duplicate_listing)
                db.commit()
            except Exception as e:
                db.rollback()
