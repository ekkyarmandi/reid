import scrapy
import traceback
from models.error import Error
from models.listing import Listing
from reid.database import get_db
from reid.func import first_month


class BaseSpider(scrapy.Spider):
    scraped_at = first_month()
    existing_urls = []
    visited_urls = []

    def handle_error(self, failure):
        if 400 <= failure.value.response.status < 500:
            self.logger.error(f"Request failed: {failure.request.url}")
            if "Ignoring non-200 response" in str(failure.value):
                # update the related listing to be not available
                db = next(get_db())
                url = failure.request.url
                listing = db.query(Listing).filter(Listing.url == url).first()
                if listing:
                    listing.is_available = False
                    listing.availability = "Delisted"
                    listing.sold_at = first_month()
                    db.commit()
                    # clear already recorded error
                    db.query(Error).filter(Error.url == url).delete()
                    db.commit()
                return
            else:
                error = Error(
                    url=failure.request.url,
                    source="Spider",
                    error_message=str(failure.value),
                )
                # Capture the traceback and add it to the error message
                tb = traceback.format_exc()
                error.error_message += f"\nTraceback:\n{tb}"
                db = next(get_db())
                try:
                    db.add(error)
                    db.commit()
                except Exception as e:
                    db.rollback()
                    self.logger.error(f"Error adding new error to database: {e}")
