#!/usr/bin/env python3
"""Check certificate hostname and lifetime separately; OpenSSL's -checkhost
prints mismatches but can still return exit code zero, so verify its result."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess


def check(path, domain, seconds):
    if not re.fullmatch(r'[a-z0-9.-]+', domain) or seconds < 0:
        raise ValueError('Invalid certificate check input')
    if not Path(path).is_file():
        return {'valid': False, 'hostname': False, 'not_expiring': False, 'message': 'Certificate file missing.'}
    environment = dict(os.environ, LC_ALL='C')
    host = subprocess.run(['openssl', 'x509', '-in', str(path), '-noout', '-checkhost', domain], capture_output=True, text=True, timeout=10, env=environment)
    match = host.returncode == 0 and f'Hostname {domain} does match certificate' in host.stdout.splitlines()
    lifetime = subprocess.run(['openssl', 'x509', '-in', str(path), '-noout', '-checkend', str(seconds)], capture_output=True, text=True, timeout=10, env=environment)
    fresh = lifetime.returncode == 0
    return {'valid': bool(match and fresh), 'hostname': match, 'not_expiring': fresh, 'message': 'Certificate hostname and lifetime checked.'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--domain', required=True)
    parser.add_argument('--seconds', type=int, default=604800)
    args = parser.parse_args()
    try: print(json.dumps(check(args.file, args.domain, args.seconds)))
    except Exception: print(json.dumps({'valid': False, 'hostname': False, 'not_expiring': False, 'message': 'Certificate could not be parsed or checked.'}))
