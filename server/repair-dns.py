#!/usr/bin/env python3
"""Check Kakakin's route; optionally reuse an existing panel Namecheap account.

No registrar keys enter argv, source, reports or environment output. Writes are
restricted to kakakin.africandroid.world -> the selected panel server IPv4.
"""
import ipaddress
import json
import os
from pathlib import Path
import signal
import socket
import stat
import sys


def local_ipv6():
    result = set()
    path = Path('/proc/net/if_inet6')
    if path.exists():
        for line in path.read_text().splitlines():
            address, _, _, scope, *_ = line.split()
            value = ipaddress.IPv6Address(int(address, 16))
            if scope == '00' and value.is_global:
                result.add(str(value))
    return result


def resolve(domain):
    records = {'a': [], 'aaaa': []}
    signal.alarm(15)
    try:
        for family, key in [(socket.AF_INET, 'a'), (socket.AF_INET6, 'aaaa')]:
            try:
                records[key] = sorted({str(ipaddress.ip_address(r[4][0])) for r in socket.getaddrinfo(domain, None, family, socket.SOCK_STREAM)})
            except socket.gaierror:
                pass
    finally:
        signal.alarm(0)
    return records


def ready(records, expected, ipv6):
    return set(records['a']) == {expected} and set(records['aaaa']).issubset(ipv6)


def provision_saved_account(config):
    if config['domain'] != 'kakakin.africandroid.world':
        raise ValueError('Automatic DNS provisioning is restricted to kakakin.africandroid.world.')
    root = Path(config.get('panel_root', '/opt/olamidepanel')).resolve()
    for path in [root, root/'panel', *[root/'panel'/f for f in ['database.py', 'payments.py', 'namecheap.py']]]:
        st = path.stat()
        if st.st_uid != 0 or st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise ValueError('Panel code must be root-owned before using its saved DNS account.')
    sys.path.insert(0, str(root/'panel'))
    from database import connect
    from payments import cipher
    from namecheap import provision
    with connect() as con:
        selected = int(config.get('account_id') or 0)
        if selected:
            row = con.execute("SELECT * FROM namecheap_accounts WHERE id=? AND mode='production'", (selected,)).fetchone()
        else:
            rows = con.execute("SELECT * FROM namecheap_accounts WHERE mode='production' ORDER BY id").fetchall()
            if len(rows) != 1:
                raise ValueError('Select a saved production Namecheap account ID; automatic selection requires exactly one.')
            row = rows[0]
    if not row:
        raise ValueError('No matching saved production DNS account exists.')
    account = json.loads(cipher().decrypt(row['credentials'].encode())) | {'mode': 'production'}
    result = provision(account, {'sld': 'africandroid', 'tld': 'world', 'hosts': 'kakakin', 'address': config['ipv4']})
    return result.get('status') != 'DNS already configured'


def run(config, resolver=resolve, provisioner=provision_saved_account):
    domain = config['domain']
    # DNS lookups only for a proper hostname; writes have the stricter restriction above.
    if not domain or len(domain) > 253 or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-.' for c in domain):
        raise ValueError('Invalid DNS hostname')
    expected = str(ipaddress.IPv4Address(config['ipv4']))
    ipv6 = {str(ipaddress.IPv6Address(v)) for v in config.get('ipv6', [])} | local_ipv6()
    records = resolver(domain)
    if ready(records, expected, ipv6):
        return dict(ready=True, changed=False, state='ready', **records, message='DNS resolves to this Kakakin server.')
    instruction = f'Add A record kakakin in africandroid.world pointing to {expected}. Remove only stale Kakakin AAAA records or provide the server IPv6.'
    if records['aaaa'] and not set(records['aaaa']).issubset(ipv6):
        return dict(ready=False, changed=False, state='manual_required', **records, message='Unverified IPv6 route. '+instruction)
    if not config.get('auto'):
        return dict(ready=False, changed=False, state='waiting_dns', **records, message=instruction)
    try:
        changed = provisioner(config)
    except (ValueError, FileNotFoundError) as exc:
        # These are our own bounded validation messages; provider/driver failures are masked below.
        return dict(ready=False, changed=False, state='manual_required', **records, message=instruction+' Configure a saved production Namecheap account in Olamidepanel, or create the record at your DNS provider.')
    except Exception:
        return dict(ready=False, changed=False, state='manual_required', **records, message=instruction+' Saved DNS provisioning could not complete. Check API access, IP allowlisting, authoritative nameservers, and conflicting records in the panel.')
    records = resolver(domain)
    ok = ready(records, expected, ipv6)
    return dict(ready=ok, changed=changed, state='ready' if ok else 'waiting_dns', **records, message='DNS record verified at the provider; waiting for resolver propagation.' if not ok else 'DNS configured and resolves to this server.')


def main():
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('DNS lookup timed out')))
    config = json.loads(sys.stdin.read(16384))
    print(json.dumps(run(config)))

if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({'ready': False, 'changed': False, 'state': 'manual_required', 'message': 'DNS preflight could not complete. Check the server resolver and the Kakakin A/AAAA records.'}))
        sys.exit(1)
