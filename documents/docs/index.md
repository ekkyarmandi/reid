# REID Data Scraping Documentation

REID is a Python‑based Scrapy project that crawls multiple Bali property websites to extract, process, and store real estate listings.

## Key Components

- **Spiders**: Navigate web pages and extract raw property data using `PropertyItem`.
- **Items**: Define the structure of scraped data.
- **Pipelines**: Clean, validate, and save data into the database (RawDataPipeline, PropertyPipeline, ListingPipeline).
- **Database**: SQLAlchemy models for RawData, Property, Listing, Error, and Report.
- **Extractors**: Custom commands for debugging and reprocessing raw data.

## Documentation

- [How to Use](how-to-use.md): Installation, running spiders, database migrations, pipelines, and extractors.
- [Development](development.md): Code structure, testing, and contribution guidelines.

## Getting Started

Install dependencies:

```bash
pip install -r requirements.txt
```

Then refer to **How to Use** for detailed instructions.
