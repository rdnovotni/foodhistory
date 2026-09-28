#!/bin/sh
set -eu

base_url=${1:-}
if [ -z "$base_url" ]; then
  echo "Usage: $0 https://history.example.com" >&2
  exit 2
fi

response=$(curl --fail --silent --show-error --max-time 20 "${base_url%/}/health")
printf '%s' "$response" | grep -q '"status":"ok"'
echo "PASS: ${base_url%/}/health"
