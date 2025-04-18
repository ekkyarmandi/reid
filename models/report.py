from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from models.base import Base
import uuid


class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=datetime.now())
    scraped_at = Column(DateTime, nullable=False)
    source = Column(String, nullable=False)
    item_scraped_count = Column(Integer, nullable=False)
    item_dropped_count = Column(Integer, nullable=False)
    response_error_count = Column(Integer, nullable=False)
    elapsed_time_seconds = Column(Integer, nullable=False)
