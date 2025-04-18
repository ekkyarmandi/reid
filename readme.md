# REID

## Install dependencies

```bash
pip install -r requirements.txt
```

## Run all spiders

```bash
sh crawl.sh
```

## Migrate database models

- Make sure the `sqlalchemy.url` variable is point to the database
- Autogenerate the migration script

```bash
alembic revision --autogenerate -m "migration message"
```

- Apply the migration script

```bash
alembic upgrade head
```

- Downgrade the migration script

```bash
alembic downgrade <revision_id>
```

> Note: alembic versions is not pushed to the repository.
> Reminder: Don't forget to create `BaseModel` in `base.py` and add the entire models in `__init__.py` file

## How it works

The system is designed to scrape property data from websites, process the data, and store it in a database. The workflow involves several key components: Spiders, Items, Pipelines, and the Database.

### Spiders

Spiders are responsible for navigating through web pages and extracting the raw data. In this system, the `UbudpropertySpider` is used to scrape property listings from the Ubud Property website. It collects URLs of property details, parses each page, and extracts relevant information such as property ID, title, location, and more. The spider uses the `ItemLoader` to populate `PropertyItem` instances with the scraped data.

Crawl command:

```bash
scrapy crawl <spider_name>
```

### Items

Items define the structure of the data that is being scraped. In this system, the `PropertyItem` class is used to represent the data model for properties. It includes fields for raw data (e.g., source, URL, HTML content) and property-specific data (e.g., property ID, title, location, price). The fields use processors to clean and format the data as it is being loaded.

### Pipelines

Pipelines are used to process the data extracted by the spiders. They perform tasks such as cleaning, validating, and storing the data in the database. The system includes several pipeline classes:

- **RawDataPipeline**: This pipeline stores the raw HTML and JSON data into the `RawData` model in the database. It also generates a report of the spider's activity, including statistics like the number of items scraped and errors encountered.

- **PropertyPipeline**: This pipeline processes the property data, transforming it to match the `Property` model. It checks for issues, defines land zoning, and handles errors by recording them in the `Error` model. If an error occurs, it rolls back the transaction and deletes the associated raw data.

- **ListingPipeline**: This pipeline processes listing data, adding it to the `Listing` model in the database. It handles updates to existing listings by checking for changes and updating the database accordingly.

To activate pipelines in `settings.py`:

- Go to `settings.py`
- Set `ITEM_PIPELINES` to the pipeline class you want to activate.
  For example:

```python
ITEM_PIPELINES = {
    ...
    'reid.pipelines.property.PropertyPipeline': 300,
}
```

### Database

The database is used to store the processed data. It includes models such as `RawData`, `Property`, `Listing`, `Error`, and `Report`. The pipelines interact with the database to add, update, and delete records as necessary.

The integration of these components allows for efficient data scraping, processing, and storage, ensuring that the property data is accurately captured and maintained.

### Extractors (Custom Command)

The `extractors` folder contains custom commands for extracting data from the `RawData` model. It uses the same `PropertyItem` class to represent the data model for properties. But it for debugging and data scraping fix purposes.

Extractor command:

```bash
scrapy extract <spider_name>
```
