#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Run on the existing Olamidepanel host. The repair bootstrap updates this checkout.
bash "${repo_dir}/scripts/hard-fix.sh" "$@"
ansible-playbook -i 'localhost,' --connection local "${repo_dir}/ansible/publish-mobile.yml"
printf '%s\n' 'Kakakin website, Android APK and African Apps Store listing deployed and checked.'
