#!/usr/bin/env python3
"""Root-only domain inventory registration using the installed panel's DB adapter.

Reads JSON stdin; database credentials remain in /etc/olamidepanel/database.json.
Never queues the panel's static site publisher or changes an existing owner.
"""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

DOMAIN = re.compile(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}')


def choose_owner(connection, domain, username=None):
    existing = connection.execute('SELECT d.id,d.owner,u.username,u.email,u.active FROM domains d JOIN users u ON u.id=d.owner WHERE d.name=? FOR UPDATE', (domain,)).fetchone()
    if existing:
        if not existing['active']:
            raise ValueError('The existing domain owner is suspended. Restore the account in Olamidepanel first.')
        if username and username != existing['username']:
            raise ValueError('This domain already belongs to another panel account. Ownership was not changed.')
        return {'id': existing['owner'], 'username': existing['username'], 'email': existing['email']}, existing
    if username:
        owner = connection.execute('SELECT id,username,email FROM users WHERE username=? AND active=1 FOR UPDATE', (username,)).fetchone()
        if not owner:
            raise ValueError('The specified panel account is missing or suspended.')
        return owner, None
    owners = connection.execute("SELECT id,username,email FROM users WHERE active=1 AND role='root' ORDER BY id FOR UPDATE").fetchall()
    if len(owners) != 1:
        raise ValueError('Specify --panel-owner USERNAME because the panel does not have exactly one active root account.')
    return owners[0], None


def register(connection, domain, username=None, apply=False):
    owner, existing = choose_owner(connection, domain, username)
    static = connection.execute('SELECT state FROM website_requests WHERE domain_id=(SELECT id FROM domains WHERE name=?)', (domain,)).fetchone()
    if static:
        raise ValueError('A static Site Publisher request already exists for this domain. Resolve that registration before deploying the Kakakin backend; it was not overwritten.')
    changed = False
    domain_id = existing['id'] if existing else None
    if apply and not existing:
        cursor = connection.execute('INSERT INTO domains(owner,name,created) VALUES(?,?,?)', (owner['id'], domain, int(time.time())))
        domain_id = cursor.lastrowid
        connection.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)', (owner['username'], 'Kakakin backend domain registered '+domain, int(time.time())))
        changed = True
    return {'ok': True, 'changed': changed, 'domain': domain, 'domain_id': domain_id, 'owner': owner['username'], 'email': owner.get('email', ''), 'hosting': 'Kakakin Docker backend; inventory only, no static publishing'}


def main():
    if os.geteuid() != 0:
        raise ValueError('Run this integration locally as root on the Olamidepanel server.')
    parser = argparse.ArgumentParser()
    parser.add_argument('--panel-root', default='/opt/olamidepanel')
    args = parser.parse_args()
    panel_root = Path(args.panel_root).resolve()
    module_path = panel_root/'panel'/'database.py'
    for path in [panel_root, panel_root/'panel', module_path]:
        info = path.stat()
        if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise ValueError('Panel application code must be root-owned and not writable by group/other before privileged integration.')
    raw = sys.stdin.read(16385)
    if len(raw) > 16384:
        raise ValueError('Configuration too large')
    config = json.loads(raw)
    domain = str(config.get('domain', '')).lower()
    if len(domain) > 253 or not DOMAIN.fullmatch(domain):
        raise ValueError('Invalid domain')
    username = config.get('owner') or None
    if username and not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', username):
        raise ValueError('Invalid panel username')
    if config.get('mode', 'inspect') not in ['inspect', 'register']:
        raise ValueError('Invalid integration mode')
    sys.path.insert(0, str(panel_root/'panel'))
    from database import connect
    with connect() as connection:
        result = register(connection, domain, username, config.get('mode') == 'register')
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Driver errors can include connection/config details. Keep those out of stdout/logs.
        message = str(exc) if isinstance(exc, (ValueError, FileNotFoundError)) else 'Panel registration failed; inspect the installed panel/database service locally.'
        print(json.dumps({'ok': False, 'error': message}), file=sys.stderr)
        sys.exit(1)
