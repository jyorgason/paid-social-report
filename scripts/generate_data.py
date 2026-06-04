"""
Paid Social Report — Data Generation Script
Queries Databricks and writes data/channel_data.json for the HTML report.

Environment variables required:
  DATABRICKS_HOST          e.g. https://adb-1234567890.1.azuredatabricks.net
  DATABRICKS_TOKEN         Personal Access Token or Service Principal secret
  DATABRICKS_HTTP_PATH     e.g. /sql/1.0/warehouses/abc123def456

Run locally:   python scripts/generate_data.py
Run via CI:    triggered by .github/workflows/refresh.yml
"""

import os
import json
import time
import requests
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HOST        = os.environ["DATABRICKS_HOST"].rstrip("/")
TOKEN       = os.environ["DATABRICKS_TOKEN"]
HTTP_PATH   = os.environ["DATABRICKS_HTTP_PATH"]
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "channel_data.json")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# Pull 18 months of daily data so JS can handle any date-range filter
LOOKBACK_DAYS = 548  # ~18 months

# ---------------------------------------------------------------------------
# Paid Social channel detection
# ad-activity rows:  ad_source + ad_type identify the channel
# funnel-event rows: SUBCHANNEL_NAME identifies the channel
# ---------------------------------------------------------------------------
CHANNEL_SQL = """
CASE
  WHEN (ad_source = 'facebook' AND ad_type = 'social')
    OR SUBCHANNEL_NAME = 'Facebook.com'  THEN 'Facebook'
  WHEN (ad_source = 'linkedin' AND ad_type = 'social')
    OR SUBCHANNEL_NAME = 'Linkedin.com'  THEN 'LinkedIn'
  WHEN (ad_source = 'google'   AND ad_type = 'youtube')
    OR SUBCHANNEL_NAME = 'Youtube.com'   THEN 'YouTube'
  WHEN (ad_source = 'reddit'   AND ad_type = 'social')
    OR SUBCHANNEL_NAME = 'Reddit.com'    THEN 'Reddit'
END
"""

PAID_SOCIAL_ROW_FILTER = """
(
  (ad_source IN ('facebook','linkedin','reddit') AND ad_type = 'social')
  OR (ad_source = 'google' AND ad_type = 'youtube')
  OR SUBCHANNEL_NAME IN ('Facebook.com','Linkedin.com','Youtube.com','Reddit.com')
)
"""

CAMPAIGN_EXCLUDE = """
NOT (
  CONTAINS(UPPER(ad_campaign_name), 'ELITE')    OR
  CONTAINS(UPPER(ad_campaign_name), 'PAY BANDS') OR
  CONTAINS(UPPER(ad_campaign_name), 'PROD')      OR
  CONTAINS(UPPER(ad_campaign_name), 'PAYCOR')    OR
  CONTAINS(UPPER(ad_campaign_name), 'ZEN')       OR
  CONTAINS(UPPER(ad_campaign_name), 'PAYCHEX')   OR
  CONTAINS(UPPER(ad_campaign_name), 'PRG')       OR
  CONTAINS(UPPER(ad_campaign_name), 'HLTH')      OR
  CONTAINS(UPPER(ad_campaign_name), 'CONST')     OR
  CONTAINS(UPPER(ad_campaign_name), 'EDU')
)
"""

def paid_social_filter():
    return f"""
    UPPER(ad_campaign_name) LIKE '%DG |%'
    AND NOT (CONTAINS(ad_campaign_name, 'BRD') OR CONTAINS(ad_group_name, 'BRD'))
    AND (ad_source IS NULL OR ad_source != 'bing')
    AND (ad_type IS NULL OR ad_type != 'search')
    AND {CAMPAIGN_EXCLUDE}
    AND {PAID_SOCIAL_ROW_FILTER}
    """

# ---------------------------------------------------------------------------
# Databricks SQL execution helpers
# ---------------------------------------------------------------------------
def run_query(sql: str) -> list[dict]:
    """Execute SQL on Databricks and return rows as list of dicts."""
    resp = requests.post(
        f"{HOST}/api/2.0/sql/statements",
        headers=HEADERS,
        json={
            "statement": sql,
            "warehouse_id": HTTP_PATH.split("/")[-1],
            "wait_timeout": "30s",
            "on_wait_timeout": "CONTINUE",
            "format": "JSON_ARRAY",
        },
    )
    resp.raise_for_status()
    body = resp.json()
    statement_id = body["statement_id"]

    # Poll until done
    while body["status"]["state"] in ("PENDING", "RUNNING"):
        time.sleep(2)
        r = requests.get(
            f"{HOST}/api/2.0/sql/statements/{statement_id}",
            headers=HEADERS,
        )
        r.raise_for_status()
        body = r.json()

    if body["status"]["state"] != "SUCCEEDED":
        raise RuntimeError(f"Query failed: {body['status']}\nSQL:\n{sql[:500]}")

    columns = [c["name"] for c in body["manifest"]["schema"]["columns"]]
    rows = []
    for chunk in body.get("result", {}).get("data_array", []):
        rows.append(dict(zip(columns, chunk)))
    return rows

# ---------------------------------------------------------------------------
# Main queries
# ---------------------------------------------------------------------------
def fetch_daily_channel_data(lookback_days: int) -> list[dict]:
    start_date = (date.today() - timedelta(days=lookback_days)).isoformat()
    sql = f"""
    WITH base AS (
      SELECT
        CAST(activity_date AS DATE)  AS activity_date,
        {CHANNEL_SQL}                AS channel,
        spend, impressions, clicks,
        MQL1, MQL1_TA, MQL2, MQL2_TA, MQL_TOTAL, MQL_TOTAL_TA,
        SAL, SAL_TA, TQL, TQL_TA,
        SAO, SAO_TA,
        CW, CW_TA, CW_MRR, CW_MRR_TA,
        DQ
      FROM analytics_us_east_2_production_sandbox_mktg.jyorgason.marketing_funnel_with_paid_daily_ads
      WHERE {paid_social_filter()}
        AND activity_date >= '{start_date}'
    )
    SELECT
      activity_date,
      channel,
      SUM(spend)       AS spend,
      SUM(impressions) AS impressions,
      SUM(clicks)      AS clicks,
      SUM(MQL1)        AS mql1,
      SUM(MQL1_TA)     AS mql1_ta,
      SUM(MQL2)        AS mql2,
      SUM(MQL2_TA)     AS mql2_ta,
      SUM(MQL_TOTAL)   AS mql_total,
      SUM(SAL)         AS sal,
      SUM(TQL)         AS tql,
      SUM(SAO)         AS sao,
      SUM(SAO_TA)      AS sao_ta,
      SUM(CW)          AS cw,
      SUM(CW_TA)       AS cw_ta,
      SUM(CW_MRR)      AS cw_mrr,
      SUM(DQ)          AS dq
    FROM base
    WHERE channel IS NOT NULL
    GROUP BY activity_date, channel
    ORDER BY activity_date DESC, channel
    """
    return run_query(sql)


def fetch_campaign_data(lookback_days: int) -> list[dict]:
    start_date = (date.today() - timedelta(days=lookback_days)).isoformat()
    sql = f"""
    WITH base AS (
      SELECT
        CAST(activity_date AS DATE)  AS activity_date,
        {CHANNEL_SQL}                AS channel,
        ad_campaign_name, ad_group_name, ad_id,
        UTM_CAMPAIGN, funnel_placement,
        spend, impressions, clicks,
        MQL1, MQL1_TA, MQL2, MQL2_TA, MQL_TOTAL,
        SAL, TQL, SAO, SAO_TA, CW, CW_TA, CW_MRR, DQ
      FROM analytics_us_east_2_production_sandbox_mktg.jyorgason.marketing_funnel_with_paid_daily_ads
      WHERE {paid_social_filter()}
        AND activity_date >= '{start_date}'
    )
    SELECT
      channel,
      ad_campaign_name,
      ad_group_name,
      SUM(spend)       AS spend,
      SUM(impressions) AS impressions,
      SUM(clicks)      AS clicks,
      SUM(MQL1)        AS mql1,
      SUM(MQL2)        AS mql2,
      SUM(MQL_TOTAL)   AS mql_total,
      SUM(SAL)         AS sal,
      SUM(SAO)         AS sao,
      SUM(CW)          AS cw,
      SUM(CW_MRR)      AS cw_mrr,
      SUM(DQ)          AS dq
    FROM base
    WHERE channel IS NOT NULL
    GROUP BY channel, ad_campaign_name, ad_group_name
    ORDER BY channel, spend DESC NULLS LAST
    """
    return run_query(sql)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f"[{datetime.utcnow().isoformat()}] Fetching daily channel data ({LOOKBACK_DAYS} days)...")
    daily = fetch_daily_channel_data(LOOKBACK_DAYS)
    print(f"  → {len(daily)} rows")

    print(f"[{datetime.utcnow().isoformat()}] Fetching campaign data...")
    campaigns = fetch_campaign_data(LOOKBACK_DAYS)
    print(f"  → {len(campaigns)} rows")

    output = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "daily": daily,
        "campaigns": campaigns,
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, default=str)

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"[{datetime.utcnow().isoformat()}] Written to {OUTPUT_FILE} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
