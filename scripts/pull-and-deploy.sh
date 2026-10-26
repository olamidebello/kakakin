#!/usr/bin/env bash
# Run ON the existing Olamidepanel host. Secrets/passwords are never arguments.
set -euo pipefail
if [[ "${1:-}" == '--help' || "${1:-}" == '-h' ]]; then
  echo "Usage: sudo bash $0 [--admin-email EMAIL] [--panel-owner USER] [--branch main] [--domain kakakin.africandroid.world] [--vars FILE] [--repair]"
  echo 'Clones/updates /opt/kakakin-bootstrap, then runs ansible/pull-and-deploy.yml locally.'
  exit 0
fi
[[ "${EUID}" == 0 ]] || { echo 'Run this script with sudo on the Olamidepanel server.' >&2; exit 77; }
[[ -f /etc/olamidepanel/database.json && -x /opt/olamidepanel/venv/bin/python ]] || { echo 'Olamidepanel must already be installed on this server.' >&2; exit 69; }
repo_url="${KAKAKIN_REPO_URL:-https://github.com/olamidebello/kakakin.git}"
case "${repo_url}" in
  https://github.com/olamidebello/kakakin.git|git@github.com:olamidebello/kakakin.git) ;;
  *) echo 'Use the Kakakin HTTPS URL or its GitHub SSH deploy-key URL.' >&2; exit 64 ;;
esac
revision='main'; forwarded=("$@")
while (($#)); do
  case "$1" in
    --repair) shift ;;
    --branch) revision="${2:?Missing branch/tag/commit}"; shift 2 ;;
    --admin-email|--panel-owner|--domain|--vars) [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 64; }; shift 2 ;;
    *) echo "Unknown argument for local deployment: $1" >&2; exit 64 ;;
  esac
done
[[ "${revision}" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ && "${revision}" != *..* ]] || { echo 'Invalid Git revision.' >&2; exit 64; }
if ! command -v git >/dev/null || ! command -v ansible-playbook >/dev/null || ! command -v flock >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y git ansible-core ca-certificates util-linux
fi
exec 9>/run/lock/kakakin-pull-and-deploy.lock
flock -n 9 || { echo 'Another Kakakin deployment is already running.' >&2; exit 75; }
checkout='/opt/kakakin-bootstrap'
export GIT_TERMINAL_PROMPT=0
if [[ ! -e "${checkout}" ]]; then
  git clone "${repo_url}" "${checkout}"
fi
[[ -d "${checkout}/.git" && ! -L "${checkout}" ]] || { echo "${checkout} is not a regular Kakakin checkout; it was not overwritten." >&2; exit 73; }
owner="$(stat -c '%u' "${checkout}")"
permissions="$(stat -c '%a' "${checkout}")"
[[ "${owner}" == 0 && $((8#${permissions} & 0022)) == 0 ]] || { echo 'The privileged deployment checkout must be root-owned and not group/other writable.' >&2; exit 77; }
remote="$(git -C "${checkout}" remote get-url origin)"
[[ "${remote}" == "${repo_url}" ]] || { echo 'Existing checkout uses a different remote. Review it locally; no remote was changed.' >&2; exit 73; }
git -C "${checkout}" diff --quiet
git -C "${checkout}" diff --cached --quiet
git -C "${checkout}" fetch --depth=1 origin "${revision}"
git -C "${checkout}" checkout --detach FETCH_HEAD
printf 'Deploying Kakakin revision %s to kakakin.africandroid.world (unless overridden).\n' "$(git -C "${checkout}" rev-parse --short HEAD)"
exec bash "${checkout}/scripts/deploy-olamidepanel.sh" "${forwarded[@]}"
