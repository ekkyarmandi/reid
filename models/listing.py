from sqlalchemy import (
    Column,
    String,
    Text,
    TIMESTAMP,
    Float,
    Boolean,
    BigInteger,
    text,
    Index,
)
import uuid
from datetime import datetime
from models.base import Base
from reid.settings import REID_CODE


class Listing(Base):
    __tablename__ = "listing"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    property_id = Column(String, nullable=True)
    reid_id = Column(String, nullable=False)
    source = Column(String, nullable=False)
    scraped_at = Column(TIMESTAMP, default=datetime.now())
    created_at = Column(TIMESTAMP, default=datetime.now())
    updated_at = Column(TIMESTAMP, default=datetime.now(), onupdate=datetime.now())
    url = Column(Text, nullable=False, unique=True)
    image_url = Column(Text, nullable=False, default="")
    title = Column(Text, nullable=True)
    description = Column(Text, nullable=False, default="")
    region = Column(String, nullable=True)
    location = Column(String, nullable=True)
    longitude = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    leasehold_years = Column(Float, nullable=True)
    contract_type = Column(String, nullable=True)
    property_type = Column(String, nullable=True)
    listed_date = Column(String, nullable=True)
    bedrooms = Column(Float, nullable=True)
    bathrooms = Column(Float, nullable=True)
    build_size = Column(Float, nullable=True)
    land_size = Column(Float, nullable=True)
    land_zoning = Column(String, nullable=True)
    price = Column(BigInteger, nullable=False)
    currency = Column(String, nullable=False)
    is_available = Column(Boolean, default=True)
    availability = Column(String, default="Available")
    is_off_plan = Column(Boolean, default=False)
    sold_at = Column(TIMESTAMP, nullable=True)
    is_excluded = Column(Boolean, default=False)
    excluded_by = Column(String, nullable=True)
    tab = Column(String, default="DATA")

    __table_args__ = (
        Index("idx_listing_url", "url", unique=True),
        Index("idx_listing_source", "source"),
        Index("idx_listing_reid_id", "reid_id"),
        Index("idx_listing_created_at", "created_at"),
        Index("idx_listing_updated_at", "updated_at"),
        Index("idx_listing_is_available", "is_available"),
        Index("idx_listing_availability", "availability"),
        Index("idx_listing_tab", "tab"),
    )

    def reid_id_generator(self, db):
        code = REID_CODE[self.source]
        # TEMPORARY FIX
        today = datetime.now().replace(day=1, year=2025)
        today = today.replace(month=today.month - 1)
        yr_mo = today.strftime(f"REID_%y_%m_{code}")
        q = text(
            "SELECT reid_id FROM listing WHERE reid_id LIKE :yr_mo ORDER BY reid_id DESC LIMIT 1;"
        )
        last_reid_id = db.execute(q, {"yr_mo": yr_mo + "%"}).fetchone()
        if last_reid_id:
            index = int(last_reid_id[0].split("_")[-1]) + 1
        else:
            index = 1
        reid_id = f"{yr_mo}_{index:03d}"
        # check url existing
        q = text(f"SELECT url FROM listing WHERE url='{self.url}';")
        existing_url = db.execute(q).fetchone()
        if not existing_url:
            self.reid_id = reid_id

    def classify_tab(self):
        if self.price >= 78656000000 and self.currency == "IDR":
            self.tab = "LUXURY LISTINGS"
        elif self.price >= 5000000 and self.currency == "USD":
            self.tab = "LUXURY LISTINGS"
        elif self.property_type == "Land":
            self.tab = "ALL LAND"
        else:
            self.tab = "DATA"

    def compare(self, new_data):
        self.changes = []
        changes = 0
        fields_to_compare = [
            "price",
            "currency",
            "availability",
            "is_available",
            "is_off_plan",
            "image_url",
            "description",
            "location",
            "leasehold_years",
            "contract_type",
            "property_type",
            "bedrooms",
            "bathrooms",
            "build_size",
            "land_size",
            "land_zoning",
            "property_id",
            "listed_date",
            "sold_at",
        ]
        for attr in fields_to_compare:
            old_value = getattr(self, attr)
            new_value = new_data.get(attr)
            if attr == "availability":
                if new_value != "Available":
                    self.changes.append(
                        {"field": "availability", "old": old_value, "new": new_value}
                    )
                    self.is_available = False
                    self.sold_at = datetime.now().replace(
                        day=1,
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0,
                    )
                    changes += 1
                    continue
            elif attr == "price" and new_value == -1:
                self.price = old_value
                continue
            # replace the value if the new value is different
            elif attr in ["leasehold_years", "sold_at"]:
                if new_value != old_value:
                    self.changes.append(
                        {"field": attr, "old": old_value, "new": new_value}
                    )
                    setattr(self, attr, new_value)
                    changes += 1
                    continue
            # fill the missing value
            if new_value and not old_value:
                self.changes.append({"field": attr, "old": old_value, "new": new_value})
                setattr(self, attr, new_value)
                changes += 1
            # override the value if the new value is different and not empty
            elif new_value and old_value and new_value != old_value:
                self.changes.append({"field": attr, "old": old_value, "new": new_value})
                setattr(self, attr, new_value)
                changes += 1
        return changes > 0

    def get_changes(self):
        return self.changes

    def __repr__(self):
        return f"<Listing UUID='{self.id}'>"

    def to_dict(self):
        # Helper function to convert datetime to timestamp (milliseconds)
        def to_timestamp(dt):
            if dt is None:
                return None
            return int(dt.timestamp() * 1000)

        # Handle price fields based on currency
        price_idr = None
        price_usd = None
        if self.currency == "USD":
            price_usd = self.price
        elif self.currency == "IDR":
            price_idr = self.price

        if self.availability == "Delisted":
            self.availability = "Sold"
            site_status = "Delisted"
        else:
            site_status = None

        return {
            "FX": None,  # Exchange rate not stored in model
            "Source A": self.source,
            "Source B": None,
            "ID": self.property_id,
            "REID ID": self.reid_id,
            "Duplicate": None,  # Set to None as requested
            "Region": self.region,
            "Location": self.location,
            "Contract Type": self.contract_type,
            "Property Type": self.property_type,
            "Years": self.leasehold_years,
            "Bedrooms": self.bedrooms,
            "Bathrooms": self.bathrooms,
            "Land Size (SQM)": self.land_size,
            "Build Size (SQM)": self.build_size,
            "FSR": None,  # Not stored in model
            "Price": price_idr,  # Only set if currency is IDR
            "Price ($)": price_usd,  # Only set if currency is USD
            "Price/SQM ($)": None,  # Calculated field not stored in model
            "Price/Year ($)": None,  # Calculated field not stored in model
            "Availability": self.availability,
            "Site Status": site_status,
            "Sold Date": to_timestamp(self.sold_at),
            "Scrape Date": to_timestamp(self.scraped_at),
            "List Date": self.listed_date,
            "Days listed": None,  # Calculated field not stored in model
            "Property Link": self.url,
            "Image": self.image_url,
            "Title": self.title,
            "Description": self.description,
            "Off plan": None,  # Not directly mapped
            "Investment": None,  # Not stored in model
            "Modern": None,  # Not stored in model
            "Brand New": None,  # Not stored in model
            "Family": None,  # Not stored in model
            "Spacious": None,  # Not stored in model
            "Enclosed Living": None,  # Not stored in model
            "Open Living": None,  # Not stored in model
            "Enclosed and Living": None,  # Not stored in model
            "Off-plan": "Yes" if self.is_off_plan else "No",
            "Pool": None,  # Not stored in model
            "Garden": None,  # Not stored in model
            "Single story": None,  # Not stored in model
            "Second story": None,  # Not stored in model
        }
