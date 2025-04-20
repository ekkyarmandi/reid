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

### Table Descriptions

- **PROPERTY**: Stores raw, unprocessed data scraped directly from various property websites. This table acts as the initial staging area before data is cleaned and processed.
  - `id`: Unique identifier for the raw property record.
  - `property_id`: Property identifier specific to the source website.
  - `source`: The name of the website the property was scraped from (e.g., "Bali Home Immo").
  - `scraped_at`: Timestamp when the data was scraped.
  - `created_at`: Timestamp when the record was first created in this table.
  - `url`: The URL of the original property listing.
  - `image_url`: URL(s) of property images.
  - `title`: Title of the property listing.
  - `description`: Description text from the listing.
  - `location`: Location details from the listing.
  - `longitude`, `latitude`: Geographic coordinates (often derived).
  - `leasehold_years`: Remaining lease years (if applicable).
  - `contract_type`: Type of ownership (e.g., "Freehold", "Leasehold").
  - `property_type`: Type of property (e.g., "Villa", "Land").
  - `listed_date`: Date the property was listed on the source site.
  - `bedrooms`, `bathrooms`: Number of bedrooms/bathrooms.
  - `build_size`, `land_size`: Size of the building and land (usually in sqm).
  - `land_zoning`: Zoning information for the land.
  - `price`: Listing price.
  - `currency`: Currency of the price (e.g., "IDR", "USD").
  - `is_available`: Boolean indicating current availability (derived).
  - `availability`: Raw availability text from the source (e.g., "Sold", "Available").
  - `is_off_plan`: Boolean indicating if the property is off-plan.
- **TAG**: Used for associating specific tags or flags with properties, potentially for categorization or workflow management (e.g., marking properties needing review).
  - `id`: Unique identifier for the tag association.
  - `created_at`, `updated_at`: Timestamps for tag creation/update.
  - `name`: The name of the tag (e.g., "Needs Review", "Duplicate Check").
  - `property_id`: Foreign key linking to the `PROPERTY` table `id`.
  - `is_solved`, `is_ignored`: Flags indicating the status of the tag.
- **LISTING**: Contains cleaned, processed, and potentially deduplicated property data derived from the `PROPERTY` table. This is the primary table for final analysis and presentation.
  - Most fields mirror the `PROPERTY` table but contain standardized and cleaned data.
  - `id`: Unique identifier for the processed listing record.
  - `reid_id`: A unique identifier generated by the REID system, potentially used for internal tracking or linking duplicates.
  - `region`: Broader geographical region (derived from `location`).
  - `sold_at`: Timestamp when the property was marked as sold.
  - `is_excluded`: Flag indicating if the listing should be excluded from certain views or analyses.
  - `excluded_by`: Reason or user who marked the listing as excluded.
  - `tab`: A field potentially used for UI categorization or filtering.
- **REPORT**: Stores summary reports for each spider run, tracking metrics like items scraped, dropped, errors, and duration.
  - `id`: Unique identifier for the report entry.
  - `created_at`: Timestamp when the report entry was created.
  - `scraped_at`: Timestamp matching the `scraped_at` time of the items in the run.
  - `source`: The name of the spider that ran.
  - `item_scraped_count`: Number of items successfully scraped.
  - `item_dropped_count`: Number of items dropped during pipeline processing.
  - `response_error_count`: Number of network/HTTP errors encountered.
  - `elapsed_time_seconds`: Total duration of the spider run.
- **QUEUE**: Manages URLs to be scraped, tracking their status (e.g., pending, processing, completed, failed).
  - `id`: Unique identifier for the queue entry.
  - `created_at`, `updated_at`: Timestamps for queue entry creation/update.
  - `url`: The unique URL to be scraped.
  - `status`: Current status of the URL in the scraping process.
- **DUPLICATE_LISTING**: Records potential duplicate listings identified during processing.
  - `id`: Unique identifier for the duplicate record.
  - `created_at`: Timestamp when the potential duplicate was identified.
  - `source_url`: URL of the listing being checked.
  - `duplicate_url`: URL of the listing identified as a potential duplicate.
- **ERROR**: Logs errors encountered during the scraping or pipeline process, linking them to the specific URL where the error occurred.
  - `id`: Unique identifier for the error log entry.
  - `url`: The URL being processed when the error occurred.
  - `source`: The stage where the error happened (e.g., "Spider", "Pipeline").
  - `error_message`: Detailed message or traceback of the error.

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
