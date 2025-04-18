from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decouple import config

DATABASE_URL = config("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_local_db():
    engine = create_engine("postgresql://postgres:postgres@localhost:5432/reid-db")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_cloud_db():
    engine = create_engine(
        "postgresql://postgres:JRwoqmlNohrxRMdkInezZOEtUFzpaUfR@mainline.proxy.rlwy.net:23469/railway"
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_checker_db():
    engine = create_engine(
        "postgresql://postgres:QelXrdrXWKwzVdkPRoHiDAAMHoGdPDkb@autorack.proxy.rlwy.net:33614/railway"
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
