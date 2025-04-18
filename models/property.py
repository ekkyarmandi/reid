from sqlalchemy import (
    Column,
    String,
    Text,
    TIMESTAMP,
    Float,
    Boolean,
    BigInteger,
    Index,
)
from sqlalchemy.orm import relationship
import uuid
import re
from datetime import datetime
from models.base import Base
from models.tags import Tag
from reid.database import get_db
from reid.settings import ZONING_COLORS, ZONING_CATEGORIES


class Property(Base):
    __tablename__ = "property"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    property_id = Column(String, nullable=True)
    source = Column(String, nullable=False)
    scraped_at = Column(TIMESTAMP, default=datetime.now())
    created_at = Column(TIMESTAMP, default=datetime.now())
    url = Column(Text, nullable=False)
    image_url = Column(Text, nullable=False, default="")
    title = Column(Text, nullable=True)
    description = Column(Text, nullable=False, default="")
    location = Column(Text, nullable=True)
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

    tags = relationship("Tag", back_populates="property")

    __table_args__ = (
        Index("idx_property_url", "url"),
        Index("idx_property_source", "source"),
        Index("idx_property_created_at", "created_at"),
        Index("idx_property_is_available", "is_available"),
        Index("idx_property_availability", "availability"),
    )

    def check_off_plan(self, labels: list = []) -> bool:
        labels.extend(
            [
                self._normalize_off_plan(self.title),
                self._normalize_off_plan(self.description),
            ]
        )
        self.is_off_plan = any(list(map(self._has_off_plan, labels)))

    def identify_issues(self):
        issues = []
        if self.bedrooms and self.bedrooms >= 13:
            label = "has_more_than_13_bedrooms"
            issues.append(label)
        if not self.bedrooms and self.property_type != "Land":
            label = "no_bedrooms"
            issues.append(label)
        if self.price == 0:
            label = "no_price"
            issues.append(label)
        if not self.title or self.title == "N/A":
            label = "no_title"
            issues.append(label)
        if not self.description:
            label = "no_description"
            issues.append(label)
        if not self.location:
            label = "no_location"
            issues.append(label)
        if self.build_size and self.land_size and self.build_size > self.land_size:
            label = "build_size_greater_than_land_size"
            issues.append(label)
        if self.contract_type == "Leasehold" and not self.leasehold_years:
            label = "no_leasehold_years"
            issues.append(label)
        if self.availability != "Available":
            label = "not_available"
            issues.append(label)
        if self.property_type not in (
            "Villa",
            "House",
            "Land",
            "Apartment",
            "Hotel",
            "Townhouse",
            "Commercial",
            "Loft",
        ):
            label = "unknown_property_type"
            issues.append(label)
        if self.property_type == "Land" and self.bedrooms and self.bedrooms > 0:
            label = "land_with_bedrooms"
            issues.append(label)
        if self.contract_type not in ("Freehold", "Leasehold", "Rental"):
            label = "unknown_contract_type"
            issues.append(label)
        if self.property_type == "Land" and not self.land_zoning:
            label = "no_land_zoning"
            issues.append(label)
        # make the list uniques
        issues = list(set(issues))
        issues = list(map(lambda label: Tag(name=label, property_id=self.id), issues))
        # create tags
        prev_issues = list(map(lambda tag: tag.name, self.tags))
        db = next(get_db())
        for tag in self.tags:
            if tag.name not in issues:
                tag.is_solved = True
                db.commit()
        for issue in issues:
            if issue.name not in prev_issues:
                try:
                    db.merge(issue)
                    db.commit()
                except Exception as e:
                    db.rollback()
                    if "UNIQUE constraint failed" not in str(e):
                        raise e

    def _has_off_plan(self, text: str) -> bool:
        off_plans = ["off plan", "offplan", "off-plan", "under construction"]
        if text:
            has_off_plan = any([i in text.strip().lower() for i in off_plans])
            return has_off_plan
        return False

    def _normalize_off_plan(self, text: str) -> str:
        if text:
            pattern = r"\boff([\s\d\w]+)plan\b"
            if result := re.search(pattern, text, re.IGNORECASE):
                keyword = result.group()
                text = re.sub(keyword, "off-plan", text)
        return text

    def define_land_zoning(self):
        if self.property_type != "Land":
            return
        # split the description into sentences
        collected = []
        for stc in self._split_text(self.description):
            # find zoning word
            if re.search(r"^zoning", stc, re.IGNORECASE):
                collected.append(stc)
        # identify zoning color
        result1 = self._identify_zone_color(collected)
        result2 = self._identify_zoning(collected)
        if result1:
            self.land_zoning = result1
        elif result2:
            self.land_zoning = result2

    def _split_text(self, text: str) -> list:
        buckets = []
        if text:
            # regex sub "\n:\n" or "\n:" to ":"
            text = re.sub(r"\n:+\n", ":", text)
            text = re.sub(r"(?<=:)\n+", " ", text).lower()
            splitted = text.split("\n")
            for line in splitted:
                cols = line.split(".")
                buckets.extend(cols)
        return buckets

    def _identify_zone_color(self, collections):
        for clr in ZONING_COLORS:
            for stc in collections:
                if clr in stc:
                    return ZONING_COLORS[clr]

    def _identify_zoning(self, collections):
        for zn in ZONING_CATEGORIES:
            for stc in collections:
                if zn in stc:
                    return ZONING_CATEGORIES[zn]
