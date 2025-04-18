How to Use

This document explains how to install dependencies, run spiders, manage database migrations, activate pipelines, and use custom extractors in the REID project.

## 1. Installation

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## 2. Running Spiders

- Run all configured spiders:

  ```bash
  sh crawl.sh
  ```

- Run a specific spider:

  ```bash
  crawl <spider_name>
  ```

  Spider name could be found below the SpiderClass

  ```python
  class KibarerSpider(BaseSpider):
      name = "kibarer"
  ```

## 3. Database Migrations

1. Configure the database URL in `alembic.ini` or via the `sqlalchemy.url` setting to point to your database.

2. Generate a new migration:

   ```bash
   alembic revision --autogenerate -m "Add description here"
   ```

3. Apply migrations:

   ```bash
   alembic upgrade head
   ```

4. Roll back to a previous revision:

   ```bash
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

## 5. Custom Extractors

Custom extractor commands allow you to process data stored in the `RawData` model:

```bash
scrapy extract <spider_name>
```

This is useful for debugging and fixing scraping issues without re-running the entire crawl.

---
