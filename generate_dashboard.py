#!/usr/bin/env python3
"""
Genera el dashboard VSL de EXMA con datos frescos de Meta Ads API.
Se ejecuta via GitHub Actions cada hora.
"""

import os
import json
import requests
from datetime import datetime, timedelta, date
from collections import defaultdict

# ── CONFIG ────────────────────────────────────────────────────────
TOKEN        = os.environ['META_ACCESS_TOKEN']
AD_ACCOUNT   = 'act_470546948127194'
API_BASE     = 'https://graph.facebook.com/v19.0'
CPL_TARGET   = 42
BUDGET       = 5000

# Campañas VSL activas
VSL_CAMPAIGNS = {
    '120244403300960123': {'name': '02 | Capta | VSL | MEX', 'market': 'LATAM'},
    '120245988412020123': {'name': '03 | Capta | VSL | MEX', 'market': 'LATAM'},
    '120245988412000123': {'name': '04 | Capta | VSL | USA',  'market': 'USA'},
}

DAYS_ES   = ['Dom','Lun','Mar','Mié','Jue','Vie','Sáb']
MONTHS_ES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']

# ── META API HELPERS ──────────────────────────────────────────────
def meta_get(path, params):
    params['access_token'] = TOKEN
    r = requests.get(f'{API_BASE}/{path}', params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_daily_insights(campaign_id, since, until):
    """Fetches daily breakdown for a single campaign."""
    data = meta_get(f'{campaign_id}/insights', {
        'fields':     'spend,impressions,clicks,actions',
        'time_increment': 1,
        'time_range': json.dumps({'since': since, 'until': until}),
        'limit':      100,
    })
    rows = []
    for d in data.get('data', []):
        leads = 0
        for a in d.get('actions', []):
            if a.get('action_type') in ('lead', 'onsite_conversion.lead_grouped',
                                         'offsite_conversion.fb_pixel_lead',
                                         'complete_registration'):
                leads += int(a.get('value', 0))
        dt = datetime.strptime(d['date_start'], '%Y-%m-%d')
        rows.append({
            'date':        d['date_start'],
            'day':         DAYS_ES[dt.weekday() % 7],  # Mon=0 in Python, Sun=6
            'spend':       float(d.get('spend', 0)),
            'leads':       leads,
            'clicks':      int(d.get('clicks', 0)),
            'impressions': int(d.get('impressions', 0)),
        })
    return rows

# ── FETCH ALL DATA ────────────────────────────────────────────────
def fetch_all():
    # Fetch from 90 days ago to today
    today = date.today()
    since = (today - timedelta(days=90)).isoformat()
    until = today.isoformat()

    combined_daily  = defaultdict(lambda: {'spend':0,'leads':0,'clicks':0,'impressions':0,'day':''})
    campaign_daily  = {}

    print(f"Fetching data {since} → {until}")

    for cid, meta in VSL_CAMPAIGNS.items():
        print(f"  Campaign: {meta['name']}...")
        try:
            rows = fetch_daily_insights(cid, since, until)
            campaign_daily[cid] = rows
            for r in rows:
                d = combined_daily[r['date']]
                d['spend']       += r['spend']
                d['leads']       += r['leads']
                d['clicks']      += r['clicks']
                d['impressions'] += r['impressions']
                d['day']          = r['day']
        except Exception as e:
            print(f"  ERROR: {e}")
            campaign_daily[cid] = []

    return combined_daily, campaign_daily

# ── BUILD JS DATA STRINGS ─────────────────────────────────────────
def build_static_daily_js(combined_daily):
    rows = sorted(combined_daily.items())
    entries = []
    for date_str, d in rows:
        entries.append(
            f"{{date:'{date_str}',day:'{d['day']}'"
            f",spend:{d['spend']:.2f},leads:{d['leads']}"
            f",clicks:{d['clicks']},impressions:{d['impressions']}}}"
        )
    return 'const STATIC_DAILY_MAY = [' + ','.join(entries) + '];\n'

def build_campaign_daily_js(campaign_daily):
    camp_entries = []
    for cid, meta in VSL_CAMPAIGNS.items():
        rows = campaign_daily.get(cid, [])
        day_entries = ','.join(
            f"{{date:'{r['date']}',spend:{r['spend']:.2f},leads:{r['leads']}"
            f",clicks:{r['clicks']},impressions:{r['impressions']}}}"
            for r in rows
        )
        camp_entries.append(
            f"{{id:'{cid}',name:'{meta['name']}',market:'{meta['market']}'"
            f",status:'ACTIVE',days:[{day_entries}]}}"
        )
    return 'const CAMPAIGN_DAILY = [' + ','.join(camp_entries) + '];\n'

def build_june_js():
    # Empty — data comes from combined_daily now
    return 'const STATIC_DAILY_JUN = [];\n'

# ── INJECT INTO HTML ──────────────────────────────────────────────
def inject_data(html, combined_daily, campaign_daily):
    now_utc = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

    new_static_daily  = build_static_daily_js(combined_daily)
    new_campaign_daily = build_campaign_daily_js(campaign_daily)
    new_june           = build_june_js()

    # Replace STATIC_DAILY_MAY
    start = html.find('const STATIC_DAILY_MAY = [')
    end   = html.find('];\n', start) + 3
    html  = html[:start] + new_static_daily + html[end:]

    # Replace STATIC_DAILY_JUN
    start = html.find('const STATIC_DAILY_JUN = [')
    end   = html.find('];\n', start) + 3
    html  = html[:start] + new_june + html[end:]

    # Replace ALL_DATA line (just references STATIC_DAILY_MAY + STATIC_DAILY_JUN)
    # Already correct since we updated the arrays above

    # Replace CAMPAIGN_DAILY
    start = html.find('const CAMPAIGN_DAILY = [')
    end   = html.find('];\n', start) + 3
    html  = html[:start] + new_campaign_daily + html[end:]

    # Update "last updated" timestamp in topbar
    html = html.replace(
        '<span class="update-info" id="update-time">No actualizado aún</span>',
        f'<span class="update-info" id="update-time">Actualizado: {now_utc}</span>'
    )

    return html

# ── MAIN ──────────────────────────────────────────────────────────
def main():
    # Read template
    template_path = 'dashboard_vsl_live.html'
    if not os.path.exists(template_path):
        # Try to find it
        for f in os.listdir('.'):
            if f.endswith('.html') and 'vsl' in f.lower():
                template_path = f
                break

    print(f"Reading template: {template_path}")
    with open(template_path, encoding='utf-8') as f:
        html = f.read()

    # Fetch live data
    combined_daily, campaign_daily = fetch_all()

    if not combined_daily:
        print("WARNING: No data fetched, keeping existing data in template")
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html)
        return

    # Report summary
    total_spend = sum(d['spend'] for d in combined_daily.values())
    total_leads = sum(d['leads'] for d in combined_daily.values())
    cpl = total_spend / total_leads if total_leads else 0
    print(f"\nSummary (last 90d): ${total_spend:.0f} spend · {total_leads} leads · CPL ${cpl:.0f}")

    # Inject data
    output_html = inject_data(html, combined_daily, campaign_daily)

    # Write output
    out_path = 'index.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(output_html)
    print(f"\nDashboard generated: {out_path} ({len(output_html):,} bytes)")
    print("Done ✓")

if __name__ == '__main__':
    main()
