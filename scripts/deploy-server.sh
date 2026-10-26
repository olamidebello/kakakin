#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(dirname "${script_dir}")"
domain="${KAKAKIN_DOMAIN:-kakakin.africandroid.com}"; admin_email=""; inventory=""; branch="main"; extra_vars=""
while (($#)); do
  case "$1" in
    --domain) domain="${2:?Missing domain}"; shift 2 ;;
    --admin-email) admin_email="${2:?Missing email}"; shift 2 ;;
    --inventory) inventory="${2:?Missing inventory file}"; shift 2 ;;
    --branch) branch="${2:?Missing branch/tag/commit}"; shift 2 ;;
    --vars) extra_vars="${2:?Missing variables file}"; shift 2 ;;
    --help|-h) echo "Usage: $0 --admin-email YOUR_EMAIL [--domain kakakin.africandroid.com] [--inventory FILE] [--branch main] [--vars VAULT_OR_YAML_FILE]"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 64 ;;
  esac
done
[[ -n "${domain}" && -n "${admin_email}" ]] || { echo "--admin-email is required. Default domain: kakakin.africandroid.com." >&2; exit 64; }
command -v ansible-playbook >/dev/null || { echo 'Install Ansible first: sudo apt-get update && sudo apt-get install -y ansible-core git' >&2; exit 69; }
vars_json="$(python3 - "${domain}" "${admin_email}" "${branch}" <<'PY'
import json,sys
print(json.dumps(dict(kakakin_domain=sys.argv[1],kakakin_admin_email=sys.argv[2],kakakin_version=sys.argv[3])))
PY
)"
args=()
if [[ -n "${inventory}" ]]; then args+=(-i "${inventory}"); else args+=(-i 'localhost,' --connection local --extra-vars 'target_hosts=localhost'); fi
if [[ -n "${extra_vars}" ]]; then args+=(--extra-vars "@${extra_vars}"); fi
exec ansible-playbook "${args[@]}" "${repo_dir}/ansible/deploy.yml" --extra-vars "${vars_json}"
