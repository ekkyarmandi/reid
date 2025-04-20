# Development

This section covers how to set up a local development environment, understand the code structure, run spiders, handle DB migrations, and contribute to the project.

## Prerequisites

- Python 3.8+
- Git
- (Optional) virtualenv

## Setup

```bash
# 1. Clone & enter repo
git clone https://github.com/ekkyarmandi/reid && cd reid

# 2. Create & activate venv
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

## Project Structure

```
.
├─ reid/ # Scrapy project
│ ├─ spiders/ # Spider definitions
│ ├─ items.py # Data models (PropertyItem, etc.)
│ ├─ pipelines/ # Data processing pipelines
│ ├─ models/ # SQLAlchemy models
│ └─ settings.py
├─ documents/ # MkDocs site
│ ├─ mkdocs.yml
│ └─ docs/
│    ├─ index.md
│    ├─ how-it-work.md
│    ├─ how-to-use.md
│    └─ development.md
├─ migrations/ # Alembic migrations
└─ scrapy.cfg
```

## Tables

```mermaid
erDiagram
    PROPERTY ||--o{ TAG : has
    PROPERTY {
        String id PK
        String property_id
        String source
        TIMESTAMP scraped_at
        TIMESTAMP created_at
        Text url
        Text image_url
        Text title
        Text description
        Text location
        Float longitude
        Float latitude
        Float leasehold_years
        String contract_type
        String property_type
        String listed_date
        Float bedrooms
        Float bathrooms
        Float build_size
        Float land_size
        String land_zoning
        BigInteger price
        String currency
        Boolean is_available
        String availability
        Boolean is_off_plan
    }
    TAG {
        String id PK
        TIMESTAMP created_at
        TIMESTAMP updated_at
        String name
        String property_id FK
        Boolean is_solved
        Boolean is_ignored
    }
    LISTING {
        String id PK
        String property_id
        String reid_id
        String source
        TIMESTAMP scraped_at
        TIMESTAMP created_at
        TIMESTAMP updated_at
        Text url UK
        Text image_url
        Text title
        Text description
        String region
        String location
        Float longitude
        Float latitude
        Float leasehold_years
        String contract_type
        String property_type
        String listed_date
        Float bedrooms
        Float bathrooms
        Float build_size
        Float land_size
        String land_zoning
        BigInteger price
        String currency
        Boolean is_available
        String availability
        Boolean is_off_plan
        TIMESTAMP sold_at
        Boolean is_excluded
        String excluded_by
        String tab
    }
    REPORT {
        String id PK
        DateTime created_at
        DateTime scraped_at
        String source
        Integer item_scraped_count
        Integer item_dropped_count
        Integer response_error_count
        Integer elapsed_time_seconds
    }
    QUEUE {
        Integer id PK
        DateTime created_at
        DateTime updated_at
        String url UK
        String status
    }
    DUPLICATE_LISTING {
        UUID id PK
        TIMESTAMP created_at
        Text source_url
        Text duplicate_url
    }
    ERROR {
        String id PK
        Text url
        String source
        Text error_message
    }
```

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "describe change"

# Apply all pending migrations
alembic upgrade head

# Roll back (if needed)
alembic downgrade <revision_id>
```

## Running Spiders

```bash
# List available spiders
scrapy list

# Run a spider
scrapy crawl <spider_name>
```
