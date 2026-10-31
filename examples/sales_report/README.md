# Sales insights report

A Parquet file of sales goes in. Each row is one sale: region, product, units, price, and status (`completed`, `refunded`, or `cancelled`). The job writes a second Parquet file, one row per region and product, with the order count, units sold, and revenue. Only completed sales count toward units and revenue. Refunded and cancelled sales still count as orders.

Flowspan records the decisions and exceptions of that job. OpenObserve, running locally, is where you look at the traces and the `flowspan.function.calls` metric.

## Run

From this directory:

```bash
docker compose up -d
pip install -r requirements.txt
python build_report.py
```

The first run writes `data/sales.parquet` (including one row with a negative price, which the job skips) and `data/insights.parquet`. Replace `data/sales.parquet` and run the script again to report on your own file.

Open [http://localhost:5080](http://localhost:5080) and sign in as `root@example.com` / `Complexpass#123`.

- **Traces.** `build_report` carries `flowspan.decisions` (`classified_sale`) and `flowspan.exceptions` (the skipped row). `publish_report` is a child span and carries `accepted_report: published`.
- **Metrics.** `flowspan.function.calls` counts the rule and helper functions, with `service.name` `sales-report`.

`OPENOBSERVE_EMAIL`, `OPENOBSERVE_PASSWORD`, and `OPENOBSERVE_OTLP_ENDPOINT` override the defaults. The endpoint defaults to `http://localhost:5080/api/default`.
