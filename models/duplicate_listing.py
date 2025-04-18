from sqlalchemy import Column, TIMESTAMP, UniqueConstraint, func, Text
import uuid
from models.base import Base
from sqlalchemy.dialects.postgresql import UUID


class DuplicateListing(Base):
    __tablename__ = "duplicate_listing"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    created_at = Column(TIMESTAMP, default=func.now())
    source_url = Column(Text, nullable=False)
    duplicate_url = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_url", "duplicate_url", name="uq_source_duplicate"),
    )
