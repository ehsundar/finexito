#!/usr/bin/env bash
# Prints the server's .env. Every key in deploy/.env.example takes the GitHub
# secret or variable of the same name, else the template's value; a key left
# empty by both fails the deploy. Run by the Deploy Action, which passes
# SECRETS and VARS as the JSON of `toJSON(secrets)` and `toJSON(vars)`.
set -euo pipefail

template=$(dirname "$0")/.env.example
missing=()

while IFS='=' read -r key default; do
  value=$(jq -rn --arg k "$key" \
    '(env.SECRETS | fromjson? // {})[$k] // (env.VARS | fromjson? // {})[$k] // empty')
  value=${value:-$default}
  if [ -z "$value" ]; then
    missing+=("$key")
  elif [[ $value == *$'\n'* ]]; then
    echo "::error::$key spans several lines, which .env cannot hold." >&2
    exit 1
  else
    printf '%s=%s\n' "$key" "$value"
  fi
done < <(grep -E '^[A-Z_][A-Z0-9_]*=' "$template")

if [ ${#missing[@]} -gt 0 ]; then
  echo "::error::Set these on the production environment in GitHub: ${missing[*]}" >&2
  exit 1
fi
