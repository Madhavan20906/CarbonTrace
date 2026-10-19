"""End-to-end demo / smoke test against a running local chain and API.

    1. cd contracts-pkg && npx hardhat node           (terminal 1)
    2. npm run deploy:local                           (terminal 2)
    3. cd backend && uvicorn app.main:app             (terminal 3)
    4. python scripts/e2e_demo.py

Walks every Fraud Lab scenario through verify -> sign -> on-chain mint, then retirement and revocation.
Uses Hardhat's publicly known dev keys. Local use only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from eth_account import Account
from eth_utils import keccak
from web3 import Web3

API = os.getenv("API_URL", "http://127.0.0.1:8000")
RPC = os.getenv("RPC_URL", "http://127.0.0.1:8545")
DEPLOY = Path(os.getenv("DEPLOYMENT_FILE", Path(__file__).resolve().parents[2] / "deployments" / "localhost.json"))

ADMIN_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
DEVS = {
    "dev-a": "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
    "dev-b": "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6",
    "buyer": "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a",
}

GREEN, RED, DIM, END = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
failures = 0


def check(cond: bool, msg: str):
    global failures
    print(f"  {GREEN}PASS{END} {msg}" if cond else f"  {RED}FAIL{END} {msg}")
    failures += 0 if cond else 1


dep = json.loads(DEPLOY.read_text())
w3 = Web3(Web3.HTTPProvider(RPC))
reg = w3.eth.contract(address=Web3.to_checksum_address(dep["address"]), abi=dep["abi"])
ERRORS = {"0x" + keccak(text=f"{e['name']}({','.join(i['type'] for i in e['inputs'])})")[:4].hex(): e["name"]
          for e in dep["abi"] if e["type"] == "error"}


def send(key: str, fn):
    acct = Account.from_key(key)
    tx = fn.build_transaction({"from": acct.address, "nonce": w3.eth.get_transaction_count(acct.address),
                               "gas": 8_000_000, "gasPrice": w3.eth.gas_price})
    raw = acct.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(raw.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(h)


def revert_name(exc: Exception) -> str:
    text = " ".join(str(a) for a in getattr(exc, "args", [])) + str(getattr(exc, "data", ""))
    for sel, name in ERRORS.items():
        if sel in text or name in text:
            return name
    return text[:120]


def mint(key: str, att: dict):
    m = att["message"]
    tup = (m["to"], m["vintage"], m["centroidLatE6"], m["centroidLonE6"], Web3.to_bytes(hexstr=m["cellsHash"]),
           int(m["tonnes"]), m["scoreBps"], Web3.to_bytes(hexstr=m["evidenceHash"]),
           Web3.to_bytes(hexstr=m["metadataHash"]), int(m["deadline"]), int(m["nonce"]))
    fn = reg.functions.mintVerified(tup, [int(c) for c in att["cells"]], att["metadataURI"], Web3.to_bytes(hexstr=att["signature"]))
    try:
        fn.call({"from": m["to"]})  # simulate first so reverts surface with a decodable reason
    except Exception as e:  # noqa: BLE001
        return None, revert_name(e)
    return send(key, fn), None


def verify(scn: dict, developer: str) -> dict:
    r = httpx.post(f"{API}/api/verify", json={**scn["request"], "developer": developer}, timeout=60)
    r.raise_for_status()
    return r.json()


def main() -> int:
    assert w3.is_connected(), f"No chain at {RPC}"
    scenarios = {s["id"]: s for s in httpx.get(f"{API}/api/scenarios").json()}
    dev_a, dev_b, buyer = (Account.from_key(DEVS[k]).address for k in ("dev-a", "dev-b", "buyer"))
    print(f"\nRegistry {reg.address} on chain {dep['chainId']} | API {API}\n")

    print("1. Legit rainforest")
    d = verify(scenarios["legit-wayanad"], dev_a)
    check(d["approved"] and d["signed"], f"AI approved with score {d['score']} for {d['verifiedTonnes']} t")
    rcpt, err = mint(DEVS["dev-a"], d["attestation"])
    check(err is None and rcpt.status == 1, "minted on-chain")
    check(reg.functions.balanceOf(dev_a, 1).call() == d["verifiedTonnes"], "developer holds the credits")

    print("2. Same land claimed again (double counting)")
    d2 = verify(scenarios["double-count"], dev_b)
    check(d2["approved"] and d2["signed"], "AI alone cannot see the duplicate (it is genuinely a forest)")
    check(d2["chainConflict"] is not None and d2["chainConflict"]["projectId"] == 1, "pre-check flags the overlap with project #1")
    rcpt, err = mint(DEVS["dev-b"], d2["attestation"])
    check(rcpt is None and err == "CellAlreadyClaimed", f"CONTRACT REJECTED the mint ({err})")

    print("3. Fraudulent claims")
    for sid in ("fake-desert", "fake-city", "cleared-forest"):
        f = verify(scenarios[sid], dev_b)
        check(not f["approved"] and f["attestation"] is None, f"{sid}: rejected, score {f['score']} ({f['capsApplied']})")

    print("4. Inflated claim is trimmed to capacity")
    t = verify(scenarios["inflated-claim"], dev_a)
    check(t["approved"] and t["verifiedTonnes"] < t["claimedTonnes"], f"claimed {t['claimedTonnes']} t, minted {t['verifiedTonnes']} t")
    rcpt, err = mint(DEVS["dev-a"], t["attestation"])
    check(err is None, "trimmed credits minted (project #2)")

    print("5. Second genuine biome")
    o = verify(scenarios["legit-oregon"], dev_b)
    rcpt, err = mint(DEVS["dev-b"], o["attestation"])
    check(err is None, "temperate forest minted (project #3)")

    print("6. Transfer, retire, revoke")
    send(DEVS["dev-a"], reg.functions.safeTransferFrom(dev_a, buyer, 1, 300, b""))
    send(DEVS["buyer"], reg.functions.retire(1, 120, "Acme Logistics", "FY2026 scope 1 offset"))
    check(reg.functions.balanceOf(buyer, 1).call() == 180, "buyer retired 120 t, 180 t left")
    send(ADMIN_KEY, reg.functions.revokeProject(2, "Independent audit could not confirm the peat forest boundary"))
    try:
        reg.functions.retire(2, 1, "x", "y").call({"from": dev_a})
        check(False, "revoked credits must not be retirable")
    except Exception as e:  # noqa: BLE001
        check(revert_name(e) == "ProjectIsRevoked", "revoked project is frozen")

    print("7. API read endpoints")
    stats = httpx.get(f"{API}/api/stats").json()
    check(stats["projects"] == 3 and stats["retired"] == 120, f"stats {stats}")
    projects = httpx.get(f"{API}/api/projects").json()
    check(len(projects) == 3 and projects[1]["revoked"], "project list reflects revocation")
    ev = httpx.get(f"{API}/api/evidence/{projects[0]['evidenceHash']}").json()
    check(ev["schema"] == "carbontrace.evidence/1", "evidence bundle retrievable by on-chain hash")
    acts = httpx.get(f"{API}/api/activity").json()
    check({a["type"] for a in acts} == {"minted", "retired", "revoked"}, f"activity feed has {len(acts)} events")

    print(f"\n{'ALL CHECKS PASSED' if not failures else str(failures) + ' CHECK(S) FAILED'}\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
