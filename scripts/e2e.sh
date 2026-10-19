#!/usr/bin/env bash
# Full local end-to-end check: chain -> deploy -> API -> fraud-lab walkthrough. Cleans up after itself.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIDS=()
cleanup() { for p in "${PIDS[@]:-}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT

cd "$ROOT/contracts-pkg"
npx hardhat node > /tmp/ct-node.log 2>&1 &
PIDS+=($!)
for i in $(seq 1 40); do
  curl -s -m 1 -X POST -H 'content-type: application/json' \
    --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' localhost:8545 >/dev/null 2>&1 && break
  sleep 0.5
done
npx hardhat run scripts/deploy.js --network localhost | grep -E "deployed|Wrote"

cd "$ROOT/backend"
# shellcheck disable=SC1091
. .venv/bin/activate
uvicorn app.main:app --port 8000 > /tmp/ct-api.log 2>&1 &
PIDS+=($!)
for i in $(seq 1 40); do curl -s -m 1 localhost:8000/api/health >/dev/null 2>&1 && break; sleep 0.5; done
python scripts/e2e_demo.py
