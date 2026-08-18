#!/usr/bin/env bash
set -e

# HA Supervisor skriver brugerens add-on-konfiguration (config.yaml's
# "options", indtastet under add-on'ets Konfiguration-fane) til
# /data/options.json ved opstart. Læses her og eksporteres som miljøvariabel
# - samme princip som INDKOBSLISTE_DB (Dockerfile), bare uden bashio, som
# resten af dette add-on heller ikke bruger.
if [ -f /data/options.json ]; then
  export ANTHROPIC_API_KEY="$(python3 -c "import json; print(json.load(open('/data/options.json')).get('anthropic_api_key', ''))")"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
