# Paid Social — Channel Performance Report

Static HTML report powered by Databricks, hosted on GitHub Pages, embeddable in Google Sites.

## What this is

Recreates the BambooHR Paid Social Weekly/Daily/Monthly channel performance report with:
- **Channels**: Facebook · LinkedIn · YouTube · Reddit · Total
- **Views**: Weekly (7 weeks) · Daily (same weekday × 7 occurrences) · Monthly
- **Metrics**: Spend, Impressions, Clicks, CTR, eCPM, eCPC, full MQL→CW funnel, cost-per metrics, conversion rates, PBP
- **Summary rows**: WoW % Change · 6-Week Avg · % vs 6-Week Avg (new vs Tableau)
- **Filters**: Start/End date, all channels

## Architecture

```
Databricks (analytics_us_east_2_production_sandbox_mktg.jyorgason.marketing_funnel_with_paid_daily_ads)
       ↓  nightly via GitHub Actions
scripts/generate_data.py  →  data/channel_data.json
       ↓
index.html  (GitHub Pages)
       ↓
Google Sites  (iframe embed)
```

## Setup

### 1. GitHub Secrets

Add these three secrets in **Settings → Secrets and variables → Actions**:

| Secret | Description | Example |
|--------|-------------|---------|
| `DATABRICKS_HOST` | Workspace URL | `https://adb-1234567890.1.azuredatabricks.net` |
| `DATABRICKS_TOKEN` | Personal Access Token | `dapi...` |
| `DATABRICKS_HTTP_PATH` | SQL Warehouse HTTP path | `/sql/1.0/warehouses/abc123` |

**To find your SQL Warehouse HTTP path:**
1. Go to Databricks workspace → SQL Warehouses
2. Click your warehouse → Connection Details
3. Copy the **HTTP Path**

**To create a Personal Access Token:**
1. User Settings → Developer → Access Tokens → Generate New Token

### 2. Enable GitHub Pages

1. Settings → Pages
2. Source: **Deploy from a branch**
3. Branch: `main` / `(root)`
4. Save — your report URL will be `https://jyorgason.github.io/paid-social-report/`

### 3. Embed in Google Sites

1. Open Google Sites → Edit page
2. Insert → Embed → **Embed URL**
3. Paste: `https://jyorgason.github.io/paid-social-report/`
4. Resize the embed block to fill the page

### 4. Initial data load

Either wait for the nightly cron, or trigger manually:
- GitHub → Actions → **Refresh Report Data** → Run workflow

### 5. Local development / data refresh

```bash
# Install deps
pip install requests

# Set env vars
export DATABRICKS_HOST="https://adb-xxxx.azuredatabricks.net"
export DATABRICKS_TOKEN="dapi..."
export DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/abc123"

# Generate data
python scripts/generate_data.py

# Serve locally
python -m http.server 8080
# Open http://localhost:8080
```

## Data source

Table: `analytics_us_east_2_production_sandbox_mktg.jyorgason.marketing_funnel_with_paid_daily_ads`

**Paid Social filter logic:**
- Campaign name contains `DG |`  
- Excludes: BRD, Bing, search ads, ELITE/PAY BANDS/PROD/PAYCOR/ZEN/PAYCHEX/PRG/HLTH/CONST/EDU campaigns
- Channel rows: `ad_source ∈ {facebook, linkedin, google/youtube, reddit}` (spend data)
- Funnel rows: `SUBCHANNEL_NAME ∈ {Facebook.com, Linkedin.com, Youtube.com, Reddit.com}` (attribution data)

## Automation schedule

The GitHub Actions workflow (`.github/workflows/refresh.yml`) runs at **06:00 UTC daily** (midnight MT).
Trigger a manual refresh anytime from the Actions tab.

## Files

```
paid-social-report/
├── .github/workflows/refresh.yml    # Nightly data refresh
├── scripts/generate_data.py         # Queries Databricks → data/channel_data.json
├── data/channel_data.json           # Auto-generated; do not edit manually
├── index.html                       # Complete report (HTML + CSS + JS)
└── README.md
```
