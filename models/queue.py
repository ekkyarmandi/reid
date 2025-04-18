from sqlalchemy import Column, Integer, String, DateTime, func
from models.base import Base


class Queue(Base):
    __tablename__ = "queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    url = Column(String, unique=True)
    status = Column(String)
