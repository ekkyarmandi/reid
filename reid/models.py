from sqlalchemy import (
    Column,
    ForeignKey,
    DateTime,
    Text,
    Integer,
    Numeric,
    Boolean,
    Enum as SQLAlchemyEnum,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

from enum import Enum

Base = declarative_base()


class CurrencyType(str, Enum):
    IDR = "IDR"
    USD = "USD"


class RawData(Base):
    __tablename__ = "raw_data"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    created_at = Column(DateTime, nullable=False, default=func.now())
    url = Column(Text)
    html = Column(Text)
    json = Column(Text)


class PropertyData(Base):
    __tablename__ = "properties"

    url = Column(Text, primary_key=True)
    scraped_at = Column(DateTime, nullable=False, default=func.now())
    sold_at = Column(DateTime, nullable=False, default=None)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )
    source = Column(Text)
    property_id = Column(Text)
    listed_date = Column(Text)
    title = Column(Text)
    region = Column(Text)
    location = Column(Text)
    longitude = Column(Numeric(10, 8), nullable=True)
    latitude = Column(Numeric(10, 8), nullable=True)
    contract_type = Column(Text)
    property_type = Column(Text)
    leasehold_years = Column(Numeric(10, 1))
    bedrooms = Column(Integer)
    bathrooms = Column(Integer)
    land_size = Column(Integer)
    build_size = Column(Integer)
    price = Column(Integer)
    currency = Column(SQLAlchemyEnum(CurrencyType))
    image_url = Column(Text)
    is_available = Column(Boolean, default=True, nullable=False)
    availability_label = Column(Text)
    description = Column(Text)
    is_off_plan = Column(Boolean, default=False, nullable=False)


class PropertyRecord(Base):
    __tablename__ = "records"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    url = Column(Text)
    scraped_at = Column(DateTime, nullable=False, default=func.now())
    sold_at = Column(DateTime, nullable=False, default=None)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime,
        nullable=False,
        default=func.now(),
        onupdate=func.now(),
    )
    source = Column(Text)
    property_id = Column(Text)
    listed_date = Column(Text)
    title = Column(Text)
    region = Column(Text)
    location = Column(Text)
    longitude = Column(Numeric(10, 8), nullable=True)
    latitude = Column(Numeric(10, 8), nullable=True)
    contract_type = Column(Text)
    property_type = Column(Text)
    leasehold_years = Column(Numeric(10, 1))
    bedrooms = Column(Integer)
    bathrooms = Column(Integer)
    land_size = Column(Integer)
    build_size = Column(Integer)
    price = Column(Integer)
    currency = Column(SQLAlchemyEnum(CurrencyType))
    image_url = Column(Text)
    is_available = Column(Boolean, default=True, nullable=False)
    availability_label = Column(Text)
    description = Column(Text)
    is_off_plan = Column(Boolean, default=False, nullable=False)
    raw_data_id = Column(
        UUID, ForeignKey("raw_data.id", ondelete="CASCADE"), nullable=False
    )
