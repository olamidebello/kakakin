# Repair Kakakin at kakakin.africandroid.world

The correct domain is **kakakin.africandroid.world**. The earlier `.com` configuration is superseded. The server remains **154.16.170.86**.

Run these commands in the server terminal. Fetch/checkout works even when the deployment checkout is detached; no `git pull` or forced reset is required:

```bash
cd /opt/kakakin-bootstrap
git fetch origin main
git checkout --detach FETCH_HEAD
bash scripts/hard-fix.sh
```

If local tracked edits prevent checkout, review them before proceeding; these commands do not discard them. The helper updates the bootstrap checkout again under a deployment lock and runs `ansible/hard-fix.yml`.

## Automatic repairs

- Changes the deployment, Nginx domain, application origin, health URL and panel registration to `kakakin.africandroid.world`.
- Recovers the existing Kakakin administrator email from its protected environment file. Existing login hashes, data, session signing key, and backups remain in place.
- Diagnoses DNS before changing the application or contacting Let's Encrypt. The expected IPv4 route is `154.16.170.86`; IPv6 records must match a global IPv6 address on this host or explicit `kakakin_public_ipv6` values.
- When DNS is missing, can reuse the panel's encrypted production Namecheap account. Automatic selection requires exactly one production account; with more than one, set `kakakin_namecheap_account_id` through `--vars`. It provisions only the `kakakin` A record in `africandroid.world` using the installed panel adapter, which preserves other records and refuses conflicting/unsupported zones. Keys are decrypted only in process memory.
- Waits up to roughly two minutes for a provisioned record to propagate, without repeating DNS writes. Missing API access, unsupported DNS, conflicting records, resolver failures, and stale AAAA records produce an actionable stop before application changes.
- Pulls the selected app revision, builds its image if needed, recreates crashed/unhealthy or misconfigured Kakakin containers, and makes the usual cold backup before migrations.
- Removes duplicate **exclusive** Kakakin vhost blocks from other enabled Nginx site files, retaining other server blocks. It backs up changed files and restores them if `nginx -t` fails. Shared blocks listing additional domains are reported instead of being deleted. The managed `/etc/nginx/sites-available/kakakin.conf` is regenerated for the corrected domain.
- Uses a distinct login rate-limit zone to avoid colliding with the older Kakakin zone name.
- Checks certificate hostname and validity. Missing, invalid, or near-expiry certificates are issued/renewed only after the DNS preflight; valid certificates are reused. Nginx is validated before reload.
- Verifies the public backend identity and database readiness, then registers the domain in Olamidepanel and writes `/var/log/kakakin/hard-fix-report.json`.

The process does not delete the old `.com` certificate, other domains, unrelated Nginx settings, application accounts, recipient consent records, or message history. It does not retry ambiguous completed/live campaign sends or weaken TLS verification. In repair mode, an existing static Site Publisher request for this exact hostname is backed up under `/var/backups/kakakin/static-publisher/` and retired to `external_backend` after DNS checks. Domain ownership and static files remain intact; the request is retained in MySQL instead of being deleted. The publisher worker lock prevents an in-flight static provisioning job from racing the takeover. Ordinary deployments still stop on an active static request.

## If DNS cannot be repaired automatically

At the authoritative DNS provider for `africandroid.world`, create:

| Type | Host | Value |
|---|---|---|
| A | kakakin | 154.16.170.86 |

A saved Namecheap account must have API access enabled, this server's outgoing IPv4 allowlisted, and control over the authoritative DNS zone. If no usable account is saved, the script cannot create a DNS record without provider access. It prints the exact record above and stops; it does not repeatedly request a certificate for a nonexistent hostname. Only remove a stale AAAA record for this Kakakin hostname, not other IPv6 records.

A generic zone management service outside Namecheap still requires its own authorized API adapter or the manual record. Existing registrar credentials are not guessed or copied into Git.

## Optional operator variables

Keep any provider secrets outside Git, preferably in an Ansible Vault file. These non-secret selectors may be passed using `--vars`:

```yaml
kakakin_namecheap_account_id: 1  # Use the actual saved production account ID.
kakakin_public_ipv4: 154.16.170.86
kakakin_public_ipv6: []
```

Use `bash scripts/hard-fix.sh --admin-email dobcalldemo@gmail.com` for an explicit login-email override. This does not change an already-initialized account's password.

## Diagnostics

```bash
cat /var/log/kakakin/hard-fix-report.json
docker logs --tail 100 kakakin
nginx -t
curl -fsS https://kakakin.africandroid.world/healthz
```

Expected public health includes `service=kakakin` and `database=ready`. A successful local syntax/unit check is not a claim that the live server has been repaired. Run this playbook on the server to perform the actual DNS, Nginx, certificate and deployment checks. Unknown global server failures and unavailable third-party credentials cannot be automatically guaranteed away.
