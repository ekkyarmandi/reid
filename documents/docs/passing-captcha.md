# Handling Cloudflare CAPTCHA for Specific Spiders

Two spiders, `balihomeimmo` and `balirealty`, are protected by Cloudflare's CAPTCHA challenge, which requires a specific approach to bypass.

## Process

1.  **Obtain `cf_clearance` Cookie:**

    - Use the `CF-Clearance-Scraper` tool (available at [https://github.com/Xewdy444/CF-Clearance-Scraper.git](https://github.com/Xewdy444/CF-Clearance-Scraper.git)) to solve the Cloudflare challenge for each website (`bali-home-immo.com` and `balirealty.com`).
    - This tool will output the necessary `cf_clearance` cookie value and the `User-Agent` string used during the process.

2.  **Update `.env` file:**

    - Copy the obtained `cf_clearance` value for Bali Home Immo into the `BALIHOMEIMMO_COOKIES` variable in your `.env` file.
    - Copy the obtained `cf_clearance` value for Bali Realty into the `BALIREALTY_COOKIES` variable in your `.env` file.
    - **Crucially**, copy the `User-Agent` string provided by the `CF-Clearance-Scraper` tool into the `USER_AGENT` variable in your `.env` file. The user agent used to get the cookie _must_ match the user agent used by the scraper.

3.  **Local Execution:**

    - These two spiders _must_ be run locally. The `cf_clearance` cookie is tied to the IP address and user agent used to obtain it, making it incompatible with the standard cloud-based proxy setup.

4.  **Disable Proxies:**

    - Before running `balihomeimmo` or `balirealty` locally, you need to disable the proxy middleware in `reid/settings.py`.
    - Comment out the following lines within the `DOWNLOADER_MIDDLEWARES` dictionary:
      ```python
      # "scrapy_proxies.RandomProxy": 200,
      # "scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware": 300,
      ```

5.  **Local Database:**

    - Since these spiders run locally, ensure you have a local database configured for the pipelines (`RawDataPipeline`, `PropertyPipeline`, `ListingPipeline`) to write data to.

6.  **Data Synchronization:**
    - After successfully running the spiders locally and storing the data in your local database, you are responsible for synchronizing this data with the cloud database. The specific method for achieving this sync is up to you.

**Important:** Remember to uncomment the proxy settings in `reid/settings.py` when running other spiders that require the cloud proxy setup.
