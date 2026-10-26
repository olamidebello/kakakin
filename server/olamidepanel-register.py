#!/usr/bin/env python3
"""Root-only domain inventory registration using the installed panel's DB adapter.

Reads JSON stdin; database credentials remain in /etc/olamidepanel/database.json.
Never queues the panel's static site publisher or changes an existing owner.
"""
import argparse
import fcntl
import contextlib
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


def register(connection, domain, username=None, apply=False, allow_static=False):
    owner, existing = choose_owner(connection, domain, username)
    static = connection.execute('SELECT state FROM website_requests WHERE domain_id=(SELECT id FROM domains WHERE name=?)', (domain,)).fetchone()
    if static and static['state'] != 'external_backend' and not (allow_static and not apply and domain == 'kakakin.africandroid.world'):
        raise ValueError('A static Site Publisher request already exists for this domain. Resolve that registration before deploying the Kakakin backend; it was not overwritten.')
    changed = False
    domain_id = existing['id'] if existing else None
    if apply and not existing:
        cursor = connection.execute('INSERT INTO domains(owner,name,created) VALUES(?,?,?)', (owner['id'], domain, int(time.time())))
        domain_id = cursor.lastrowid
        connection.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)', (owner['username'], 'Kakakin backend domain registered '+domain, int(time.time())))
        changed = True
    return {'ok': True, 'changed': changed, 'domain': domain, 'domain_id': domain_id, 'owner': owner['username'], 'email': owner.get('email', ''), 'hosting': 'Kakakin Docker backend; inventory only, no static publishing'}


def retire_static(connection, domain, username=None, backup=None):
    if domain != 'kakakin.africandroid.world':
        raise ValueError('Static takeover is restricted to kakakin.africandroid.world.')
    owner, existing = choose_owner(connection, domain, username)
    static = connection.execute('SELECT * FROM website_requests WHERE domain_id=(SELECT id FROM domains WHERE name=?) FOR UPDATE', (domain,)).fetchone()
    if not static or static['state'] == 'external_backend':
        return {'ok': True, 'changed': False, 'domain': domain, 'owner': owner['username']}
    if backup is None:
        raise ValueError('A completed backup is required before retiring the static publisher.')
    saved = backup({'domain': domain, 'owner': owner['username'], 'domain_id': existing['id'], 'static_request': dict(static)})
    connection.execute("UPDATE website_requests SET state='external_backend',message=?,updated=? WHERE domain_id=?", ('Static publishing retired for Kakakin backend deployment', int(time.time()), existing['id']))
    connection.execute('INSERT INTO audit(actor,action,created) VALUES(?,?,?)', (owner['username'], 'Kakakin repair retired static publisher '+domain, int(time.time())))
    return {'ok': True, 'changed': True, 'domain': domain, 'owner': owner['username'], 'backup': saved}


def backup_static(record):
    directory = Path('/var/backups/kakakin/static-publisher')
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    info = directory.stat()
    if directory.is_symlink() or info.st_uid != 0 or info.st_mode & 0o077:
        raise ValueError('Static publisher backup directory must be root-owned and private.')
    path = directory/('domain-'+str(record['domain_id'])+'-'+str(time.time_ns())+'.json')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as file:
        json.dump(record, file, indent=2, default=str)
        file.flush()
        os.fsync(file.fileno())
    return str(path)


@contextlib.contextmanager
def publisher_lock():
    directory = Path('/var/lib/olamidepanel-provisioner')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = directory.stat()
    if directory.is_symlink() or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('Publisher worker state directory is not trusted.')
    lock = directory/'worker.lock'
    if lock.is_symlink(): raise ValueError('Unsafe publisher lock path')
    with lock.open('a') as file:
        deadline = time.monotonic()+120
        while True:
            try:
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ValueError('Static publisher worker is still busy. Retry after its current job completes; no static request was changed.')
                time.sleep(1)
        yield


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
    if config.get('mode', 'inspect') not in ['inspect', 'register', 'retire_static']:
        raise ValueError('Invalid integration mode')
    sys.path.insert(0, str(panel_root/'panel'))
    from database import connect
    lock = publisher_lock() if config.get('mode') == 'retire_static' else contextlib.nullcontext()
    with lock:
        with connect() as connection:
            if config.get('mode') == 'retire_static':
                result = retire_static(connection, domain, username, backup_static)
            else:
                result = register(connection, domain, username, config.get('mode') == 'register', bool(config.get('allow_static')))
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Driver errors can include connection/config details. Keep those out of stdout/logs.
        message = str(exc) if isinstance(exc, (ValueError, FileNotFoundError)) else 'Panel registration failed; inspect the installed panel/database service locally.'
        print(json.dumps({'ok': False, 'error': message}), file=sys.stderr)
        sys.exit(1)
