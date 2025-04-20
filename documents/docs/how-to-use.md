How to Use

This document explains how to install dependencies, run spiders, manage database migrations, activate pipelines, and use custom extractors in the REID project.

## 1. Installation

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## 2. Running Spiders

- Run all configured spiders:

```
bash crawl.sh
```

- Run a specific spider:

```
bash crawl <spider_name>
```

Spider name could be found below the SpiderClass

```
class KibarerSpider(BaseSpider):
    name = "kibarer"
```

## 3. Database Migrations

- Configure the database URL in `alembic.ini` or via the `sqlalchemy.url` setting to point to your database.

- Generate a new migration:

```
alembic revision --autogenerate -m "Add description here"
```

- Apply migrations:

```
alembic upgrade head
```

- Roll back to a previous revision:

```
alembic downgrade <revision_id>
```

> **Note**: Alembic migration scripts are not committed to the repository. Before generating migrations, ensure a `BaseModel` exists in `models/base.py` and all model classes are imported in `models/__init__.py`.

## 4. Activating Pipelines

Pipelines are configured in `reid/settings.py`. Edit the `ITEM_PIPELINES` setting to enable desired pipelines:

```python
ITEM_PIPELINES = {
    'reid.pipelines.raw.RawDataPipeline': 100,
    'reid.pipelines.property.PropertyPipeline': 200,
    'reid.pipelines.listing.ListingPipeline': 300,
}
```

Adjust the order and include only the pipelines you wish to activate.
