#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(dirname "${script_dir}")"
domain="${KAKAKIN_DOMAIN:-kakakin.africandroid.com}"; admin_email=""; panel_owner=""; inventory=""; branch="main"; extra_vars=""
while (($#)); do
  case "$1" in
    --domain) domain="${2:?Missing domain}"; shift 2 ;;
    --admin-email) admin_email="${2:?Missing email}"; shift 2 ;;
    --panel-owner) panel_owner="${2:?Missing panel username}"; shift 2 ;;
    --inventory) inventory="${2:?Missing inventory file}"; shift 2 ;;
    --branch) branch="${2:?Missing revision}"; shift 2 ;;
    --vars) extra_vars="${2:?Missing variables file}"; shift 2 ;;
    --help|-h) echo "Usage: $0 [--admin-email EMAIL] [--panel-owner USERNAME] [--domain kakakin.africandroid.com] [--inventory FILE] [--branch main] [--vars FILE]"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 64 ;;
  esac
done
command -v ansible-playbook >/dev/null || { echo 'Install Ansible first: sudo apt-get update && sudo apt-get install -y ansible-core git' >&2; exit 69; }
vars_json="$(python3 - "${domain}" "${admin_email}" "${panel_owner}" "${branch}" <<'PY'
import json,sys
values={'kakakin_domain':sys.argv[1],'kakakin_version':sys.argv[4]}
if sys.argv[2]: values['kakakin_admin_email']=sys.argv[2]
if sys.argv[3]: values['kakakin_panel_owner']=sys.argv[3]
print(json.dumps(values))
PY
)"
args=()
if [[ -n "${inventory}" ]]; then args+=(-i "${inventory}"); else args+=(-i 'localhost,' --connection local --extra-vars 'target_hosts=localhost'); fi
if [[ -n "${extra_vars}" ]]; then args+=(--extra-vars "@${extra_vars}"); fi
exec ansible-playbook "${args[@]}" "${repo_dir}/ansible/pull-and-deploy.yml" --extra-vars "${vars_json}"
