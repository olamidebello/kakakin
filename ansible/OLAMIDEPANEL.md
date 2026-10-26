# Host Kakakin on Olamidepanel

Target: **kakakin.africandroid.com**, on the existing Olamidepanel server **154.16.170.86** (`server.dobhrap.com`). This is a fresh Kakakin installation; it does not migrate data from the old panel server.

## DNS

In the `africandroid.com` DNS zone, point `kakakin` to `154.16.170.86` with an A record. Only retain an AAAA record if that same server actually serves the app over IPv6. DNS changes are not performed by these scripts.

## Run on the panel server

Install Ansible if needed, then clone to a bootstrap directory separate from the managed checkout:

```bash
sudo apt-get update
sudo apt-get install -y git ansible-core
git clone https://github.com/olamidebello/kakakin.git /opt/kakakin-bootstrap
cd /opt/kakakin-bootstrap
sudo bash scripts/deploy-olamidepanel.sh
```

If already cloned, enter that bootstrap directory, run `git pull --ff-only`, and rerun the final command. The playbook itself pulls the requested app revision into `/opt/kakakin/source`.

The existing panel account owning the domain is preserved. For a new domain, the integration selects the single active panel-root account. If multiple root accounts exist, specify the intended owner explicitly:

```bash
sudo bash scripts/deploy-olamidepanel.sh --panel-owner owner
```

It uses that account's contact email for Kakakin's initial administrator login. Override it with `--admin-email YOUR_EMAIL`. If the panel email is missing, the playbook asks for one locally. First installation prompts privately for a new password; existing Kakakin accounts and passwords are preserved on updates. Kakakin's login is separate from the panel login.

For a private GitHub repository, prepare a read-only deploy key/verified GitHub SSH host key on the server and use a variables file with `kakakin_repo: git@github.com:olamidebello/kakakin.git`. Do not paste access tokens into shell commands or commit them.

## What this integration does

1. Requires the existing panel's MySQL configuration, database adapter, and Python environment at `/opt/olamidepanel`.
2. Checks domain ownership without transferring existing inventory records or overwriting a static Site Publisher request.
3. Pulls Kakakin, builds its Docker image, preserves its persistent database/account files, and makes a pre-update cold backup.
4. Runs the backend at host loopback `127.0.0.1:18770` and configures only the Kakakin domain in Nginx.
5. Obtains HTTPS through Let's Encrypt, enables renewal, and verifies that public `/healthz` identifies the Kakakin service with its database ready.
6. Adds the domain to the selected panel account's Domains inventory using the existing panel database adapter, and records an audit event. Repeated runs do not duplicate the domain or audit entry.
7. Saves `/etc/olamidepanel/apps/kakakin.json` as an operator manifest with the repository, deployed commit, owner, container, port, and health path. It is an operator record; the existing panel does not render an application-management GUI from this file.

**Do not submit this domain to the panel's static Site Publisher.** Kakakin needs its running backend. If a static publisher job already exists, the integration stops before app deployment and leaves the existing job unchanged. Resolve that registration first. The integration does not update or restart the Olamidepanel application, replace MySQL, grant extra panel permissions, or modify other domains.

## Remote Ansible execution

The provided inventory selects the current panel host:

```bash
ansible-playbook -i ansible/inventory.olamidepanel.ini ansible/olamidepanel.yml
```

SSH authentication and verified host keys must already be available on the control machine. No passwords or SSH keys are shipped in Git. The wrapper also accepts `--inventory`, `--branch`, and `--vars`.

## Operations

```bash
sudo docker logs --tail 100 kakakin
sudo docker inspect --format '{{.State.Health.Status}}' kakakin
sudo nginx -t
curl -fsS https://kakakin.africandroid.com/healthz
```

Expected health fields: `status=ok`, `database=ready`, `service=kakakin`.

See [the server guide](README.md) for storage locations, account administration, backup/recovery and provider secrets. Live WhatsApp/SMS campaigns still require configured business-provider credentials, approved templates where applicable, and recorded recipient consent. The application's background scheduler runs independently of browser visits.

## Verification boundary

The registration policy is unit-tested with an in-memory adapter, and both playbooks pass Ansible syntax checks. This is not a claim of a live panel/MySQL deployment. The authoring environment could not reach this server over SSH; the exact connection error was `Network is unreachable`. Public DNS/HTTPS could not be verified from that environment. Run the server-side command above to perform installation and live checks on the target.
