# Local Business Lead Generator

Builds a clean, de-duplicated list of local businesses in one niche and area, enriched with
contact e-mails, social profiles and the online booking system each business uses.

Demo run: **independent barbershops in Greater London**.

## What it does

1. **Collects** businesses from OpenStreetMap (Overpass API) for any area and category.
2. **Cleans** the data: normalises phones (+44 format) and URLs, removes duplicates
   (same website, same phone, or same name + postcode) and merges their details.
3. **Separates chains** from independents using a configurable list.
4. **Enriches** every website: visits the home and contact pages, finds the business e-mail,
   Instagram and Facebook, and detects the booking platform (Fresha, Booksy, Treatwell, Setmore, Square…).
5. **Checks e-mail domains** can receive mail (MX lookup).
6. **Exports** a formatted Excel report (Leads, Summary, Excluded chains), a CSV,
   and a masked sample that is safe to share.

The "Online booking" column is a ready sales insight: shops with a website but no booking system are
prime prospects for a booking bot or website.

## Run

```bash
bash run.command            # macOS / Linux: installs dependencies and runs
# or
pip install -r requirements.txt
python leadgen.py config.json
```

Change the niche or area in `config.json` (`area_name`, `osm_filters`, `exclude_chains`).

## Data & compliance

- Business data © OpenStreetMap contributors, Open Database License (ODbL).
- Only business contact details published by the businesses themselves are collected; no personal data.
- The crawler identifies itself, visits at most four pages per site and runs with limited concurrency.
- For client projects that need Google Maps data, the same pipeline can use the official Google Places API
  with the client's own key.
