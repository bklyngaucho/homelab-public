#!/usr/bin/env python3
"""
hl.py — Homelab API helper (runs on Mac, called via Desktop Commander)

Usage:
  python3 hl.py health                        # parallel health check all services
  python3 hl.py <service> status              # single service status + version
  python3 hl.py <service> health              # ARR health issues (sonarr/radarr/prowlarr)
  python3 hl.py <service> logs [N]            # last N log entries via API (default 20)
  python3 hl.py <service> command <name> [k=v...]  # post command to ARR service
  python3 hl.py radarr movie <id>             # fetch movie record by ID
  python3 hl.py radarr refresh <id>           # RescanMovie + RefreshMovie for ID
  python3 hl.py technitium records [zone]     # list DNS records
  python3 hl.py technitium addrecord <domain> <ip>  # add A record
  python3 hl.py idrac sensors                 # CPU temps + fan RPMs
  python3 hl.py idrac sel                     # last 20 SEL events
  python3 hl.py plex sessions                 # active Plex sessions

Services: sonarr radarr radarr4k bazarr prowlarr tautulli plex stirling-pdf technitium idrac
"""

import sys
import os
import json
import ssl
import base64
import argparse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime

# ─── Credentials ────────────────────────────────────────────────────────────

ENV_FILE = Path(__file__).parent / '.hl.env'

def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                env[k.strip()] = v.strip()
    return env

ENV = load_env()

NAS01   = ENV.get('NAS01_HOST', '192.168.1.33')
IDRAC  = ENV.get('IDRAC_HOST', '192.168.1.4')

SERVICES = {
    'sonarr':       {'host': NAS01,  'port': 8989,  'type': 'arr',        'key': ENV.get('SONARR_API_KEY', '')},
    'radarr':       {'host': NAS01,  'port': 7878,  'type': 'arr',        'key': ENV.get('RADARR_API_KEY', '')},
    'radarr4k':     {'host': NAS01,  'port': 7070,  'type': 'arr',        'key': ENV.get('RADARR4K_API_KEY', '')},
    'bazarr':       {'host': NAS01,  'port': 6767,  'type': 'bazarr',     'key': ENV.get('BAZARR_API_KEY', '')},
    'prowlarr':     {'host': NAS01,  'port': 9696,  'type': 'arr',        'key': ENV.get('PROWLARR_API_KEY', '')},
    'tautulli':     {'host': NAS01,  'port': 8181,  'type': 'tautulli',   'key': ENV.get('TAUTULLI_API_KEY', '')},
    'plex':         {'host': NAS01,  'port': 32400, 'type': 'plex',       'key': ENV.get('PLEX_TOKEN', '')},
    'stirling-pdf': {'host': NAS01,  'port': 8585,  'type': 'stirling',   'key': ENV.get('STIRLING_API_KEY', '')},
    'technitium':   {'host': NAS01,  'port': 5380,  'type': 'technitium', 'key': ENV.get('TECHNITIUM_TOKEN', '')},
    'idrac':        {'host': IDRAC, 'port': 443,   'type': 'idrac',      'key': ''},
    'seerr':        {'host': NAS01,  'port': 5055,  'type': 'seerr',      'key': ENV.get('SEERR_API_KEY', '')},
}

# ─── HTTP helpers ────────────────────────────────────────────────────────────

def _ssl_ctx(verify=True):
    if verify:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def http_get(url, headers=None, timeout=10, verify_ssl=True):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx(verify_ssl)) as r:
            return r.status, r.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')

def http_post(url, data, headers=None, timeout=10, verify_ssl=True):
    body = json.dumps(data).encode()
    hdrs = {'Content-Type': 'application/json', **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=hdrs, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx(verify_ssl)) as r:
            return r.status, r.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')

def http_put(url, data, headers=None, timeout=10, verify_ssl=True):
    body = json.dumps(data).encode()
    hdrs = {'Content-Type': 'application/json', **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=hdrs, method='PUT')
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx(verify_ssl)) as r:
            return r.status, r.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')

def jget(url, **kw):
    code, body = http_get(url, **kw)
    return code, json.loads(body) if body else {}

def jpost(url, data, **kw):
    code, body = http_post(url, data, **kw)
    return code, json.loads(body) if body else {}

def jput(url, data, **kw):
    code, body = http_put(url, data, **kw)
    return code, json.loads(body) if body else {}

# ─── Per-service health checks ───────────────────────────────────────────────

def check_arr(name, svc):
    host, port, key = svc['host'], svc['port'], svc['key']
    # Prowlarr uses v1; Sonarr/Radarr/Bazarr use v3
    for ver in ('v3', 'v1'):
        code, d = jget(f'http://{host}:{port}/api/{ver}/system/status?apikey={key}')
        if code == 200:
            return {'status': 'ok', 'version': d.get('version', '?')}
    return {'status': 'error', 'error': f'HTTP {code}'}

def check_bazarr(name, svc):
    host, port, key = svc['host'], svc['port'], svc['key']
    code, d = jget(f'http://{host}:{port}/api/system/status',
                   headers={'X-API-KEY': key})
    if code == 200:
        ver = d.get('data', d).get('bazarr_version', '?')
        return {'status': 'ok', 'version': ver}
    return {'status': 'error', 'error': f'HTTP {code}'}

def check_tautulli(name, svc):
    host, port, key = svc['host'], svc['port'], svc['key']
    code, d = jget(f'http://{host}:{port}/api/v2?apikey={key}&cmd=get_server_info')
    if code == 200 and d.get('response', {}).get('result') == 'success':
        ver = d['response'].get('data', {}).get('pms_version', '?')
        return {'status': 'ok', 'version': f'pms={ver}'}
    return {'status': 'error', 'error': d.get('response', {}).get('message', f'HTTP {code}')}

def check_plex(name, svc):
    host, port, key = svc['host'], svc['port'], svc['key']
    code, body = http_get(f'http://{host}:{port}/',
                          headers={'X-Plex-Token': key, 'Accept': 'application/json'})
    if code == 200:
        try:
            d = json.loads(body)
            ver = d.get('MediaContainer', {}).get('version', '?')
        except Exception:
            ver = 'running'
        return {'status': 'ok', 'version': ver}
    return {'status': 'error', 'error': f'HTTP {code}'}

def check_stirling(name, svc):
    host, port, key = svc['host'], svc['port'], svc['key']
    code, d = jget(f'http://{host}:{port}/api/v1/info/status',
                   headers={'X-API-Key': key})
    if code == 200:
        return {'status': 'ok', 'version': d.get('version', '?')}
    return {'status': 'error', 'error': f'HTTP {code}'}

def check_technitium(name, svc):
    host, port, key = svc['host'], svc['port'], svc['key']
    code, d = jget(f'http://{host}:{port}/api/user/session/get?token={key}')
    if code == 200 and d.get('status') == 'ok':
        ver = d.get('info', {}).get('version', '?')
        return {'status': 'ok', 'version': ver}
    return {'status': 'error', 'error': d.get('errorMessage', f'HTTP {code}')}

def check_idrac(name, svc):
    host = svc['host']
    user = ENV.get('IDRAC_USER', 'root')
    pw   = ENV.get('IDRAC_PASS', '')
    creds = base64.b64encode(f'{user}:{pw}'.encode()).decode()
    code, d = jget(f'https://{host}/redfish/v1/Systems/System.Embedded.1',
                   headers={'Authorization': f'Basic {creds}'}, verify_ssl=False)
    if code == 200:
        health = d.get('Status', {}).get('Health', '?')
        power  = d.get('PowerState', '?')
        return {'status': 'ok', 'version': f'Health={health} Power={power}'}
    return {'status': 'error', 'error': f'HTTP {code}'}

def check_seerr(name, svc):
    host, port, key = svc['host'], svc['port'], svc['key']
    hdrs = {'X-Api-Key': key} if key else {}
    code, d = jget(f'http://{host}:{port}/api/v1/status', headers=hdrs)
    if code == 200:
        return {'status': 'ok', 'version': d.get('version', '?')}
    return {'status': 'error', 'error': f'HTTP {code}'}

CHECKERS = {
    'arr':        check_arr,
    'bazarr':     check_bazarr,
    'tautulli':   check_tautulli,
    'plex':       check_plex,
    'stirling':   check_stirling,
    'technitium': check_technitium,
    'idrac':      check_idrac,
    'seerr':      check_seerr,
}

def check_service(name):
    svc = SERVICES[name]
    checker = CHECKERS.get(svc['type'])
    if not checker:
        return {'name': name, 'status': 'unknown', 'version': '', 'error': 'no checker'}
    try:
        r = checker(name, svc)
        r['name'] = name
        return r
    except Exception as e:
        return {'name': name, 'status': 'unreachable', 'version': '', 'error': str(e)[:80]}

# ─── Commands ────────────────────────────────────────────────────────────────

def cmd_health(names=None):
    targets = names or list(SERVICES.keys())
    results = {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(check_service, n): n for n in targets}
        for f in as_completed(futs):
            r = f.result()
            results[r['name']] = r

    icons = {'ok': '✅', 'error': '❌', 'unreachable': '❌', 'unknown': '⚠️'}
    print(f"\n{'Service':<16} {'Status':<12} {'Version / Info':<28} Notes")
    print('─' * 72)
    for n in targets:
        r = results.get(n, {'status': '?', 'version': '', 'error': 'missing'})
        icon = icons.get(r.get('status', '?'), '⚠️')
        ver  = (r.get('version') or '')[:26]
        err  = (r.get('error')   or '')[:24]
        note = err if r.get('status') != 'ok' else ''
        print(f"{icon} {n:<14} {r.get('status','?'):<12} {ver:<28} {note}")
    print()


def _arr_ver(name):
    """Return 'v1' for prowlarr, 'v3' for everything else."""
    return 'v1' if name == 'prowlarr' else 'v3'

def cmd_arr_health(name):
    """Show ARR health endpoint issues."""
    svc = SERVICES[name]
    host, port, key = svc['host'], svc['port'], svc['key']
    ver = _arr_ver(name)
    code, items = jget(f'http://{host}:{port}/api/{ver}/health?apikey={key}')
    if code != 200:
        print(f'Error {code}')
        return
    if not items:
        print(f'✅ {name}: no health issues')
        return
    print(f'\n{name} health issues ({len(items)}):')
    for item in items:
        lvl = item.get('type', '?').upper()
        src = item.get('source', '?')
        msg = item.get('message', '?')
        print(f'  [{lvl}] {src}: {msg}')
    print()


def cmd_arr_logs(name, tail=20):
    svc = SERVICES[name]
    host, port, key = svc['host'], svc['port'], svc['key']
    ver = _arr_ver(name)
    code, d = jget(f'http://{host}:{port}/api/{ver}/log?apikey={key}&pageSize={tail}&sortKey=time&sortDir=desc')
    if code != 200:
        print(f'Error {code}')
        return
    records = d.get('records', [])
    print(f'\n{name} logs (last {len(records)}):')
    for r in records:
        ts   = r.get('time', '')[:19].replace('T', ' ')
        lvl  = r.get('level', '?')[:5].upper()
        msg  = r.get('message', '')[:120]
        exc  = r.get('exception', '')
        line = f'  {ts}  [{lvl}]  {msg}'
        if exc:
            line += f'\n    {exc[:100]}'
        print(line)
    print()


def cmd_bazarr_logs(tail=20):
    svc = SERVICES['bazarr']
    host, port, key = svc['host'], svc['port'], svc['key']
    code, d = jget(f'http://{host}:{port}/api/system/logs?apikey={key}',
                   headers={'X-API-KEY': key})
    if code != 200:
        print(f'Error {code}')
        return
    records = d.get('data', [])[:tail]
    print(f'\nbazarr logs (last {len(records)}):')
    for r in records:
        ts  = r.get('timestamp', '')[:19]
        lvl = r.get('type', '?').upper()
        msg = r.get('message', '')[:120]
        print(f'  {ts}  [{lvl}]  {msg}')
    print()


def cmd_arr_command(name, command_name, extra_kwargs=None):
    svc = SERVICES[name]
    host, port, key = svc['host'], svc['port'], svc['key']
    ver = _arr_ver(name)
    payload = {'name': command_name, **(extra_kwargs or {})}
    code, d = jpost(f'http://{host}:{port}/api/{ver}/command?apikey={key}', payload)
    if code in (200, 201):
        cmd_id = d.get('id', '?')
        state  = d.get('status', '?')
        print(f'✅ {name}: command "{command_name}" queued (id={cmd_id}, state={state})')
    else:
        print(f'❌ Error {code}: {json.dumps(d)[:200]}')


def cmd_radarr_movie(movie_id):
    svc = SERVICES['radarr']
    host, port, key = svc['host'], svc['port'], svc['key']
    code, d = jget(f'http://{host}:{port}/api/v3/movie/{movie_id}?apikey={key}')
    if code != 200:
        print(f'Error {code}')
        return
    print(json.dumps({
        'id':        d.get('id'),
        'title':     d.get('title'),
        'year':      d.get('year'),
        'path':      d.get('path'),
        'hasFile':   d.get('hasFile'),
        'status':    d.get('status'),
        'monitored': d.get('monitored'),
        'tmdbId':    d.get('tmdbId'),
    }, indent=2))


def cmd_radarr_update_path(movie_id, new_path):
    """Fetch full movie record, update path, PUT back."""
    svc = SERVICES['radarr']
    host, port, key = svc['host'], svc['port'], svc['key']
    code, d = jget(f'http://{host}:{port}/api/v3/movie/{movie_id}?apikey={key}')
    if code != 200:
        print(f'Fetch error {code}'); return
    old = d.get('path', '')
    d['path'] = new_path
    pcode, pd = jput(f'http://{host}:{port}/api/v3/movie/{movie_id}?apikey={key}', d)
    if pcode in (200, 202):
        print(f'✅ path updated: {old!r} → {new_path!r}')
    else:
        print(f'❌ PUT error {pcode}: {str(pd)[:200]}')


def cmd_technitium_records(zone=None):
    svc = SERVICES['technitium']
    host, port, key = svc['host'], svc['port'], svc['key']
    url = f'http://{host}:{port}/api/zones/records/get?token={key}'
    if zone:
        url += f'&domain={zone}'
    else:
        url += '&domain=yourdomain.com'
    code, d = jget(url)
    if code != 200 or d.get('status') != 'ok':
        print(f'Error {code}: {d.get("errorMessage","?")}')
        return
    records = d.get('response', {}).get('records', [])
    print(f'\nDNS records ({len(records)}):')
    for r in records:
        rtype = r.get('type', '?')
        name  = r.get('name', '?')
        rdata = r.get('rData', {})
        val   = rdata.get('ipAddress') or rdata.get('nameServer') or rdata.get('value') or str(rdata)[:40]
        ttl   = r.get('ttl', '?')
        print(f'  {rtype:<6} {name:<40} {val:<20} ttl={ttl}')
    print()


def cmd_technitium_addrecord(domain, ip):
    svc = SERVICES['technitium']
    host, port, key = svc['host'], svc['port'], svc['key']
    url = (f'http://{host}:{port}/api/zones/records/add?token={key}'
           f'&type=A&domain={domain}&ipAddress={ip}&ttl=3600')
    code, d = jget(url)
    if code == 200 and d.get('status') == 'ok':
        print(f'✅ Added A record: {domain} → {ip}')
    else:
        print(f'❌ Error {code}: {d.get("errorMessage", str(d)[:200])}')


def cmd_idrac_sensors():
    host = IDRAC
    user = ENV.get('IDRAC_USER', 'root')
    pw   = ENV.get('IDRAC_PASS', '')
    creds = base64.b64encode(f'{user}:{pw}'.encode()).decode()
    hdrs  = {'Authorization': f'Basic {creds}'}

    # Temperatures
    code, d = jget(f'https://{host}/redfish/v1/Chassis/System.Embedded.1/Thermal',
                   headers=hdrs, verify_ssl=False)
    if code == 200:
        print('\nTemperatures:')
        for t in d.get('Temperatures', []):
            name  = t.get('Name', '?')
            val   = t.get('ReadingCelsius', '?')
            state = t.get('Status', {}).get('State', '?')
            if state == 'Enabled':
                print(f'  {name:<40} {val}°C')
        print('\nFans:')
        for f in d.get('Fans', []):
            name  = f.get('FanName', f.get('Name', '?'))
            rpm   = f.get('Reading', '?')
            state = f.get('Status', {}).get('State', '?')
            if state == 'Enabled':
                print(f'  {name:<40} {rpm} RPM')
    else:
        print(f'Thermal error {code}')

    # Power
    code, d = jget(f'https://{host}/redfish/v1/Chassis/System.Embedded.1/Power',
                   headers=hdrs, verify_ssl=False)
    if code == 200:
        print('\nPower:')
        for ps in d.get('PowerSupplies', []):
            name   = ps.get('Name', '?')
            watts  = ps.get('PowerInputWatts', ps.get('LastPowerOutputWatts', '?'))
            state  = ps.get('Status', {}).get('Health', '?')
            pstate = ps.get('PowerSupplyType', '')
            print(f'  {name:<30} {watts}W  Health={state}  {pstate}')
    print()


def cmd_idrac_sel(count=20):
    host  = IDRAC
    user  = ENV.get('IDRAC_USER', 'root')
    pw    = ENV.get('IDRAC_PASS', '')
    creds = base64.b64encode(f'{user}:{pw}'.encode()).decode()
    hdrs  = {'Authorization': f'Basic {creds}'}
    code, d = jget(f'https://{host}/redfish/v1/Managers/iDRAC.Embedded.1/LogServices/Sel/Entries?$top={count}',
                   headers=hdrs, verify_ssl=False)
    if code != 200:
        print(f'SEL error {code}'); return
    entries = d.get('Members', [])
    print(f'\niDRAC SEL (last {len(entries)} events):')
    for e in reversed(entries):
        ts  = e.get('Created', '')[:19].replace('T', ' ')
        sev = e.get('Severity', '?')
        msg = e.get('Message', '')[:100]
        print(f'  {ts}  [{sev:<8}]  {msg}')
    print()


def cmd_plex_sessions():
    svc = SERVICES['plex']
    host, port, key = svc['host'], svc['port'], svc['key']
    code, body = http_get(f'http://{host}:{port}/status/sessions',
                          headers={'X-Plex-Token': key, 'Accept': 'application/json'})
    if code != 200:
        print(f'Error {code}'); return
    try:
        d = json.loads(body)
        mc = d.get('MediaContainer', {})
        sessions = mc.get('Metadata', [])
        count    = mc.get('size', len(sessions))
    except Exception:
        print(body[:500]); return

    print(f'\nPlex active sessions: {count}')
    for s in sessions:
        title  = s.get('grandparentTitle') or s.get('title', '?')
        ep     = f" – {s.get('title','')}" if s.get('type') == 'episode' else ''
        user   = s.get('User', {}).get('title', '?')
        player = s.get('Player', {}).get('title', '?')
        state  = s.get('Player', {}).get('state', '?')
        print(f'  {user:<20} {title}{ep}  [{state}]  via {player}')
    if not sessions:
        print('  (none)')
    print()


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_kvargs(args):
    """Parse k=v strings into a dict, converting numeric values."""
    out = {}
    for a in args:
        if '=' in a:
            k, _, v = a.partition('=')
            try:
                v = int(v)
            except ValueError:
                pass
            out[k] = v
    return out


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return

    cmd = argv[0].lower()

    # ── health ───────────────────────────────────────────────────────────────
    if cmd == 'health':
        names = argv[1:] if len(argv) > 1 else None
        cmd_health(names)
        return

    # ── service subcommand ───────────────────────────────────────────────────
    if cmd not in SERVICES:
        print(f'Unknown service or command: {cmd!r}')
        print(f'Known services: {", ".join(SERVICES)}')
        sys.exit(1)

    name = cmd
    svc  = SERVICES[name]
    sub  = argv[1].lower() if len(argv) > 1 else 'status'

    if sub == 'status':
        r = check_service(name)
        icon = '✅' if r.get('status') == 'ok' else '❌'
        print(f'\n{icon} {name}: status={r.get("status")} version={r.get("version","")}')
        if r.get('error'):
            print(f'   error: {r["error"]}')
        print()

    elif sub == 'health':
        if svc['type'] == 'arr':
            cmd_arr_health(name)
        else:
            print(f'{name} does not have an ARR health endpoint; try "status"')

    elif sub == 'logs':
        tail = int(argv[2]) if len(argv) > 2 else 20
        if name == 'bazarr':
            cmd_bazarr_logs(tail)
        elif svc['type'] == 'arr':
            cmd_arr_logs(name, tail)
        else:
            print(f'Logs via API not supported for {name}; use SSH → docker logs {name}')

    elif sub == 'command':
        if len(argv) < 3:
            print('Usage: hl.py <arr-service> command <CommandName> [key=value ...]')
            sys.exit(1)
        cmd_name = argv[2]
        extra    = parse_kvargs(argv[3:])
        if svc['type'] != 'arr':
            print(f'{name} is not an ARR service')
            sys.exit(1)
        cmd_arr_command(name, cmd_name, extra)

    elif sub == 'refresh' and name in ('radarr', 'radarr4k'):
        if len(argv) < 3:
            print('Usage: hl.py radarr refresh <movieId>')
            sys.exit(1)
        mid = int(argv[2])
        cmd_arr_command(name, 'RefreshMovie', {'movieId': mid})
        cmd_arr_command(name, 'RescanMovie',  {'movieId': mid})

    elif sub == 'refresh' and name == 'sonarr':
        if len(argv) < 3:
            print('Usage: hl.py sonarr refresh <seriesId>')
            sys.exit(1)
        sid = int(argv[2])
        cmd_arr_command(name, 'RefreshSeries', {'seriesId': sid})

    elif sub == 'movie' and name in ('radarr', 'radarr4k'):
        if len(argv) < 3:
            print('Usage: hl.py radarr movie <movieId>')
            sys.exit(1)
        cmd_radarr_movie(int(argv[2]))

    elif sub == 'setpath' and name in ('radarr', 'radarr4k'):
        if len(argv) < 4:
            print('Usage: hl.py radarr setpath <movieId> <new_path>')
            sys.exit(1)
        cmd_radarr_update_path(int(argv[2]), argv[3])

    elif sub == 'records' and name == 'technitium':
        zone = argv[2] if len(argv) > 2 else None
        cmd_technitium_records(zone)

    elif sub == 'addrecord' and name == 'technitium':
        if len(argv) < 4:
            print('Usage: hl.py technitium addrecord <domain> <ip>')
            sys.exit(1)
        cmd_technitium_addrecord(argv[2], argv[3])

    elif sub == 'sensors' and name == 'idrac':
        cmd_idrac_sensors()

    elif sub == 'sel' and name == 'idrac':
        tail = int(argv[2]) if len(argv) > 2 else 20
        cmd_idrac_sel(tail)

    elif sub == 'sessions' and name == 'plex':
        cmd_plex_sessions()

    else:
        print(f'Unknown subcommand {sub!r} for {name}')
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
