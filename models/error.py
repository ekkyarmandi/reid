from models.base import Base
from sqlalchemy import Column, String, TIMESTAMP, Text, UniqueConstraint
import uuid


class Error(Base):
    __tablename__ = "error"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(Text, nullable=False)
    source = Column(String, nullable=False)
    error_message = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("url", "error_message", name="uq_url_error_message"),
    )
