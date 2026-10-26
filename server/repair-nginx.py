#!/usr/bin/env python3
"""Move only exclusive target-domain virtual hosts to Kakakin's managed config.

Other server blocks are retained. Changes are backed up and reverted if nginx -t
fails. The helper never reloads Nginx; the deployment does so after writing the
new route. Shared multi-domain server blocks require explicit operator review.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
import time


def mask(text):
    out = list(text)
    quote = None
    comment = False
    escaped = False
    for i, char in enumerate(text):
        if comment:
            if char == '\n': comment = False
            else: out[i] = ' '
        elif quote:
            out[i] = ' '
            if escaped: escaped = False
            elif char == '\\': escaped = True
            elif char == quote: quote = None
        elif char in ['"', "'"]:
            quote = char
            out[i] = ' '
        elif char == '#':
            comment = True
            out[i] = ' '
    return ''.join(out)


def remove_exclusive_blocks(text, domain):
    clean = mask(text)
    spans = []
    for match in re.finditer(r'\bserver\s*\{', clean):
        start = match.start()
        depth = 1
        pos = match.end()
        while pos < len(clean) and depth:
            if clean[pos] == '{': depth += 1
            elif clean[pos] == '}': depth -= 1
            pos += 1
        if depth: raise ValueError('Unbalanced Nginx server block; no file changed.')
        names = []
        for directive in re.finditer(r'\bserver_name\b([^;]*);', clean[match.end():pos-1]):
            a = match.end()+directive.start(1)
            b = match.end()+directive.end(1)
            names += [n.lower() for n in shlex.split(text[a:b], comments=True)]
        if domain not in names: continue
        if set(names) != {domain}:
            raise ValueError('The target shares a server block with other domains. No automatic takeover was performed.')
        spans.append((start, pos))
    if not spans: return text, 0
    for a, b in reversed(spans): text = text[:a]+'\n# Kakakin target route moved to its managed configuration.\n'+text[b:]
    if not re.search(r'\bserver\s*\{', mask(text)):
        text = re.sub(r'\blimit_req_zone\b[^;]*\bzone=(?:kakakin_login|kakakin_campaign_login):[^;]*;', '', text)
    return text, len(spans)


def atomic_write(path, content, info):
    descriptor, temporary = tempfile.mkstemp(prefix='.kakakin-repair-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as file: file.write(content)
        os.chmod(temporary, stat.S_IMODE(info.st_mode))
        os.chown(temporary, info.st_uid, info.st_gid)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    if os.geteuid() != 0: raise ValueError('Run Nginx repair locally as root.')
    parser = argparse.ArgumentParser()
    parser.add_argument('--domain', required=True)
    parser.add_argument('--managed', default='/etc/nginx/sites-available/kakakin.conf')
    parser.add_argument('--backup-root', default='/var/backups/kakakin')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9.-]+', args.domain): raise ValueError('Invalid domain')
    managed = Path(args.managed).resolve()
    plans = {}
    for directory in ['/etc/nginx/sites-enabled', '/etc/nginx/conf.d']:
        for entry in Path(directory).glob('*.conf' if directory.endswith('/conf.d') else '*'):
            if not entry.is_file(): continue
            path = entry.resolve()
            if path == managed or path in plans: continue
            info = path.stat()
            text = path.read_text()
            updated, count = remove_exclusive_blocks(text, args.domain)
            if not count: continue
            if info.st_uid != 0 or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                raise ValueError('Conflicting Nginx file is not trusted root-owned code; no file changed.')
            plans[path] = (text, updated, info, count)
    if not plans:
        print(json.dumps({'changed': False, 'removed_blocks': 0})); return
    backup = Path(args.backup_root)/('nginx-repair-'+time.strftime('%Y%m%dT%H%M%S')+'-'+str(os.getpid()))
    backup.mkdir(parents=True, mode=0o700)
    for path in plans:
        shutil.copy2(path, backup/(hashlib.sha256(str(path).encode()).hexdigest()[:12]+'-'+path.name))
    changed = []
    try:
        for path, (_, updated, info, _) in plans.items():
            atomic_write(path, updated, info); changed.append(path)
        result = subprocess.run([shutil.which('nginx') or '/usr/sbin/nginx', '-t'], capture_output=True, text=True, timeout=30)
        if result.returncode: raise ValueError('Nginx validation failed. Targeted edits have been restored; inspect nginx -t for the remaining configuration problem.')
    except Exception:
        for path in changed:
            original, _, info, _ = plans[path]
            atomic_write(path, original, info)
        raise
    report = {'changed': True, 'removed_blocks': sum(v[3] for v in plans.values()), 'files': [str(p) for p in plans], 'backup': str(backup)}
    (backup/'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(json.dumps({'error': str(exc)}))
        raise SystemExit(1)
