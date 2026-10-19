import dataclasses

import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data
from fastapi.testclient import TestClient

from app.attest import ATTESTATION_TYPES, DOMAIN_TYPES, canonical_json, keccak_hex
from app.config import Settings
from app.main import create_app
from app.scenarios import SCENARIOS

DEV = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
REGISTRY = "0x5FbDB2315678afecb367f032d93F642f64180aa3"


class FakeChain:
    chain_id = 31337
    address = REGISTRY

    def __init__(self, settings):
        self.conflict = None

    def connected(self):
        return True

    def info(self):
        return {"chainId": 31337, "address": REGISTRY, "network": "test", "deployBlock": 0, "verifier": None}

    def find_conflict(self, vintage, cells):
        return self.conflict


def make_client(tmp_path, **kw):
    settings = dataclasses.replace(Settings(), data_dir=tmp_path, **kw)
    holder = {}

    def factory(s):
        holder["chain"] = FakeChain(s)
        return holder["chain"]

    app = create_app(settings, chain_factory=factory)
    return TestClient(app), settings, holder


def body(scn_id, **over):
    scn = next(s for s in SCENARIOS if s["id"] == scn_id)
    return {**scn["request"], "developer": DEV, **over}


def test_approved_response_is_signed_by_the_verifier_and_verifiable(tmp_path):
    with make_client(tmp_path)[0] as c:
        s = make_client(tmp_path)[1]
        r = c.post("/api/verify", json=body("legit-wayanad"))
        assert r.status_code == 200
        d = r.json()
        assert d["approved"] and d["signed"] and d["simulated"] is True
        att = d["attestation"]
        msg = {**att["message"], "tonnes": int(att["message"]["tonnes"]), "deadline": int(att["message"]["deadline"]),
               "nonce": int(att["message"]["nonce"])}
        full = {
            "types": {"EIP712Domain": DOMAIN_TYPES, "Attestation": ATTESTATION_TYPES},
            "primaryType": "Attestation",
            "domain": {"name": "CarbonTraceRegistry", "version": "1", "chainId": 31337, "verifyingContract": REGISTRY},
            "message": msg,
        }
        recovered = Account.recover_message(encode_typed_data(full_message=full), signature=att["signature"])
        assert recovered == Account.from_key(s.verifier_private_key).address == att["signer"]
        assert msg["scoreBps"] == d["score"] * 100 and msg["to"] == DEV
        assert [int(x) for x in att["cells"]] == sorted(int(x) for x in att["cells"])


def test_rejected_scenarios_get_no_attestation(tmp_path):
    with make_client(tmp_path)[0] as c:
        for sid in ("fake-desert", "fake-city", "cleared-forest"):
            d = c.post("/api/verify", json=body(sid)).json()
            assert not d["approved"] and not d["signed"] and d["attestation"] is None
            assert "rejected" in d["explanation"]


def test_inflated_claim_is_trimmed_in_the_signed_amount(tmp_path):
    with make_client(tmp_path)[0] as c:
        d = c.post("/api/verify", json=body("inflated-claim")).json()
        assert d["signed"] and d["verifiedTonnes"] < d["claimedTonnes"]
        assert int(d["attestation"]["message"]["tonnes"]) == d["verifiedTonnes"]


def test_evidence_hash_commits_to_the_stored_bundle(tmp_path):
    with make_client(tmp_path)[0] as c:
        d = c.post("/api/verify", json=body("legit-wayanad")).json()
        bundle = c.get(f"/api/evidence/{d['evidenceHash']}")
        assert bundle.status_code == 200
        assert keccak_hex(bundle.content) == d["evidenceHash"]  # raw bytes re-hash to the committed hash
        assert keccak_hex(canonical_json(bundle.json())) == d["evidenceHash"]
        assert bundle.json()["assessment"]["score"] == d["score"]
        assert c.get("/api/evidence/0x" + "ab" * 32).status_code == 404
        assert c.get("/api/evidence/not-a-hash").status_code == 404


def test_conflict_is_reported_and_signing_follows_policy(tmp_path):
    client, _, holder = make_client(tmp_path)
    with client as c:
        holder["chain"].conflict = {"cell": 5, "projectId": 1}
        d = c.post("/api/verify", json=body("double-count")).json()
        assert d["approved"] and d["signed"] and d["chainConflict"]["projectId"] == 1  # demo mode: contract is the judge

    client, _, holder = make_client(tmp_path, refuse_on_conflict=True)
    with client as c:
        holder["chain"].conflict = {"cell": 5, "projectId": 1}
        d = c.post("/api/verify", json=body("double-count")).json()
        assert d["approved"] and not d["signed"] and "overlaps project #1" in d["explanation"]


@pytest.mark.parametrize("patch,field", [
    ({"developer": "not-an-address"}, "developer"),
    ({"claimed_tonnes": 0}, "claimed_tonnes"),
    ({"vintage": 1999}, "vintage"),
    ({"name": "x"}, "name"),
    ({"project_type": "mining"}, "project_type"),
])
def test_request_validation(tmp_path, patch, field):
    with make_client(tmp_path)[0] as c:
        r = c.post("/api/verify", json=body("legit-wayanad", **patch))
        assert r.status_code == 422 and field in r.text


def test_bad_polygon_returns_readable_error(tmp_path):
    with make_client(tmp_path)[0] as c:
        r = c.post("/api/verify", json=body("legit-wayanad", polygon=[[0, 0], [0.01, 0.01], [0.01, 0], [0, 0.01], [0, 0]]))
        assert r.status_code == 422 and "cross" in r.json()["detail"]


def test_health_config_and_scenarios(tmp_path):
    client, *_ = make_client(tmp_path)
    with client as c:
        assert c.get("/api/health").json()["chainConnected"] is True
        cfg = c.get("/api/config").json()
        assert cfg["simulated"] is True and cfg["approveThreshold"] == 70 and cfg["address"] == REGISTRY
        assert len(c.get("/api/scenarios").json()) == len(SCENARIOS)


def test_missing_chain_is_a_clear_503(tmp_path):
    from app.chain import ChainUnavailable

    def boom(settings):
        raise ChainUnavailable("no deployment")

    settings = dataclasses.replace(Settings(), data_dir=tmp_path)
    with TestClient(create_app(settings, chain_factory=boom)) as c:
        assert c.get("/api/projects").status_code == 503
        assert c.post("/api/verify", json=body("fake-desert")).status_code == 200  # rejection needs no chain
        assert c.post("/api/verify", json=body("legit-wayanad")).status_code == 503  # signing does
