# Kakakin server deployment

This playbook pulls `https://github.com/olamidebello/kakakin.git`, builds the chosen revision, and runs Kakakin on one Debian/Ubuntu server. It does not deploy to Cloudflare or upload source to ChatGPT Sites.

## Requirements

- A Debian/Ubuntu server with root/sudo access and Docker-compatible CPU/kernel.
- A domain with A/AAAA records pointing to that server. Remove stale AAAA records.
- Ports 80 and 443 reachable for Nginx and Let's Encrypt. SSH access for remote deployment.
- Enough resources for a Node/Vite Docker build; 4 GB RAM plus swap is a practical starting point.
- Ansible Core on the machine running the command. The playbook installs Docker, Git, Nginx, Certbot, and system dependencies on the target.
- For a private repository, configure a read-only GitHub deploy key and verified GitHub SSH host key on the server, then set `kakakin_repo` to `git@github.com:olamidebello/kakakin.git`. No GitHub credentials belong in the playbook.

## Run on the server

Clone the repository to a bootstrap directory, then run:

```bash
sudo apt-get update
sudo apt-get install -y git ansible-core
git clone https://github.com/olamidebello/kakakin.git kakakin-bootstrap
cd kakakin-bootstrap
sudo bash scripts/deploy-server.sh \
  --domain YOUR_REAL_DOMAIN \
  --admin-email YOUR_ADMIN_EMAIL
```

The first run prompts privately for a new administrator password of at least 14 characters. Later deploys preserve the existing account and session signing key. The configured email is explicitly allowlisted for the initial super administrator role. The playbook never resets an existing password.

## Deploy remotely

```bash
cp ansible/inventory.example.ini ansible/inventory.ini
cp ansible/group_vars/kakakin.example.yml ansible/group_vars/kakakin.yml
# Edit inventory.ini with the server address and group_vars/kakakin.yml with your domain/email.
ansible-playbook -i ansible/inventory.ini ansible/deploy.yml
```

Use `--ask-become-pass` if your remote account needs an interactive sudo password. For unattended first install, supply `kakakin_admin_password` through an Ansible Vault encrypted file and pass `--ask-vault-pass`; do not pass the password on the command line or commit it. Ordinary updates require no password variable.

## Updates

Run the same command again. The default revision is `main`. To deploy a pinned release or commit:

```bash
sudo bash scripts/deploy-server.sh --domain YOUR_REAL_DOMAIN --admin-email YOUR_ADMIN_EMAIL --branch YOUR_COMMIT_SHA
```

The playbook refuses to discard local checkout edits. It builds the image before stopping the old app. Before migration it stops Kakakin and makes a cold archive of the state and account configuration. It then starts the chosen image, waits for health, and verifies the domain through Nginx. An unchanged container is kept running. Other Nginx sites are preserved; a domain already configured elsewhere causes a clear failure instead of duplicate virtual hosts.

## Data and service locations

| Resource | Default |
|---|---|
| Source | `/opt/kakakin/source` |
| Persistent SQLite/D1 state | `/var/lib/kakakin` |
| Password hashes | `/etc/kakakin/accounts.json` |
| Server secrets | `/etc/kakakin/server.env` |
| Session signing key | `/etc/kakakin/session.key` |
| Pre-update backups | `/var/backups/kakakin` |
| Nginx site | `/etc/nginx/sites-available/kakakin.conf` |
| Docker container | `kakakin` |
| Host application binding | `127.0.0.1:18770` |
| Health check | `https://YOUR_REAL_DOMAIN/healthz` |

The container uses UID/GID 10001. Docker automatically restarts it after a host reboot. The application gateway runs the scheduler every 60 seconds independently of open browser tabs. Only explicitly authorized due campaigns are eligible, and all provider, consent, pause, and sending-limit checks remain enforced.

The server adapter uses Cloudflare's workerd runtime through Miniflare with persistent local SQLite state. This is a **single-server deployment**, not managed Cloudflare D1, a replicated database, or a high-availability cluster. Keep the state volume persistent. Do not run multiple replicas against the same directory. Back up the state and accounts together and test restores before depending on them.

## Provider secrets

Use `kakakin_provider_env` in a Vault-encrypted vars file. For example, variable names (not real values):

```yaml
kakakin_provider_env:
  WHATSAPP_TOKEN: "..."
  WHATSAPP_PHONE_ID: "..."
  WHATSAPP_API_VERSION: "..."
  META_APP_SECRET: "..."
  WEBHOOK_VERIFY_TOKEN: "..."
  TWILIO_ACCOUNT_SID: "..."
  TWILIO_AUTH_TOKEN: "..."
  TWILIO_FROM: "+..."
```

Pass it using `--vars /path/to/vault.yml` with the wrapper, or `--extra-vars @/path/to/vault.yml --ask-vault-pass` directly with Ansible. The wrapper supports non-encrypted vars files; use direct Ansible for interactive Vault password entry. Environment files are root-readable only. Provider secrets are not included in Docker images or browser responses. Configure the provider's public signed callback URLs after TLS is working:

- Meta: `https://YOUR_REAL_DOMAIN/api/webhooks/meta`
- Twilio: `https://YOUR_REAL_DOMAIN/api/webhooks/twilio`

Do not enable live sending until provider approval/registration, template wording, consent evidence, and inbound opt-out callbacks have been tested. No live delivery is enabled merely by deployment.

## Add/reset/disable a server login

Platform roles and tenant invitations remain managed in the GUI. Server login passwords are administered locally. The CLI reads JSON through stdin, stores a scrypt hash, and invalidates prior sessions for that account. This example prompts without echoing a password and sends it directly to the account tool; it does not put the password in shell arguments:

```bash
sudo python3 -c 'import getpass,json; f=open("/dev/tty","r+"); f.write("Email: "); f.flush(); email=f.readline().strip(); password=getpass.getpass("New password: "); print(json.dumps({"email":email,"password":password}))' | sudo docker run --rm -i --user 10001:10001 --env ACCOUNTS_FILE=/config/accounts.json --volume /etc/kakakin:/config:rw "$(sudo docker inspect --format '{{.Config.Image}}' kakakin)" node server/accounts.mjs
```

The account's email must then be invited to an appropriate workspace through the GUI. To disable a server login, pass `{"email":"...","disabled":true}` to the same stdin CLI. Reset/disable operations take effect on the next request.

## Diagnostics and recovery

```bash
sudo docker logs --tail 100 kakakin
sudo docker inspect --format '{{.State.Health.Status}}' kakakin
sudo nginx -t
sudo certbot renew --dry-run
```

Migration files are checksum-tracked and applied once. Changed applied migrations fail startup. If startup fails after a schema change, the playbook preserves the backup and reports failure; it does not automatically roll back data or repeat ambiguous outbound sends. Inspect provider message records before repairing a campaign stuck in `sending`. Stop the container before manually restoring a backup, restore both data and configuration to their original absolute locations, and restart the compatible image. Backups contain sensitive contacts and credentials; keep them private. Backup retention, off-site backups, firewall policy, monitoring, and disaster recovery remain operator responsibilities.
