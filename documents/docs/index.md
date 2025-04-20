# REID Data Scraping Documentation

REID is a Python‑based Scrapy project that crawls multiple Bali property websites to extract, process, and store real estate listings.

## Key Components

- **Spiders**: Navigate web pages and extract raw property data using `PropertyItem`.
- **Items**: Define the structure of scraped data.
- **Pipelines**: Clean, validate, and save data into the database (RawDataPipeline, PropertyPipeline, ListingPipeline).
- **Database**: SQLAlchemy models for RawData, Property, Listing, Error, and Report.

## Documentation

- [How to Use](how-to-use.md): Installation, running spiders, database migrations, and pipelines.
- [Development](development.md): Code structure, testing, and contribution guidelines.
