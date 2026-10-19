"""Read-only access to the CarbonTraceRegistry contract."""
from __future__ import annotations

import json
from functools import cached_property

from web3 import Web3

from .config import Settings


class ChainUnavailable(RuntimeError):
    pass


class Chain:
    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.deployment_file.exists():
            raise ChainUnavailable(
                f"Deployment file {settings.deployment_file} not found. Run `npm run deploy:local` in contracts-pkg."
            )
        dep = json.loads(settings.deployment_file.read_text())
        self.deployment = dep
        self.w3 = Web3(Web3.HTTPProvider(settings.rpc_url, request_kwargs={"timeout": 15}))
        self.address = Web3.to_checksum_address(dep["address"])
        self.contract = self.w3.eth.contract(address=self.address, abi=dep["abi"])
        self._project_fields = [o["name"] for o in next(
            x for x in dep["abi"] if x.get("name") == "projects" and x["type"] == "function")["outputs"]]

    @cached_property
    def chain_id(self) -> int:
        return int(self.deployment["chainId"])

    def connected(self) -> bool:
        try:
            return self.w3.is_connected()
        except Exception:
            return False

    def info(self) -> dict:
        return {"chainId": self.chain_id, "address": self.address, "network": self.deployment.get("network"),
                "deployBlock": self.deployment.get("deployBlock", 0), "verifier": self.deployment.get("verifier")}

    def find_conflict(self, vintage: int, cells: list[int]) -> dict | None:
        conflict, cell, pid = self.contract.functions.findConflict(vintage, cells).call()
        return {"cell": int(cell), "projectId": int(pid)} if conflict else None

    def _project(self, pid: int) -> dict:
        raw = self.contract.functions.projects(pid).call()
        p = dict(zip(self._project_fields, raw))
        return {
            "id": pid,
            "developer": p["developer"],
            "vintage": int(p["vintage"]),
            "scoreBps": int(p["scoreBps"]),
            "revoked": bool(p["revoked"]),
            "lat": int(p["centroidLatE6"]) / 1e6,
            "lon": int(p["centroidLonE6"]) / 1e6,
            "cellCount": int(p["cellCount"]),
            "mintedAt": int(p["mintedAt"]),
            "tonnes": int(p["tonnes"]),
            "retired": int(p["retired"]),
            "evidenceHash": "0x" + bytes(p["evidenceHash"]).hex(),
            "metadataURI": p["metadataURI"],
        }

    def project(self, pid: int) -> dict | None:
        count = self.contract.functions.projectCount().call()
        if pid < 1 or pid > count:
            return None
        return self._project(pid)

    def projects(self) -> list[dict]:
        count = self.contract.functions.projectCount().call()
        return [self._project(i) for i in range(1, count + 1)]

    def stats(self) -> dict:
        c = self.contract.functions
        minted, retired, revoked, count = c.totalMinted().call(), c.totalRetired().call(), c.totalRevoked().call(), c.projectCount().call()
        return {"projects": int(count), "minted": int(minted), "retired": int(retired), "revoked": int(revoked),
                "outstanding": int(minted - retired - revoked)}

    def activity(self, limit: int = 30) -> list[dict]:
        start = int(self.deployment.get("deployBlock", 0))
        ev = self.contract.events
        out: list[dict] = []
        for log in ev.ProjectMinted().get_logs(from_block=start):
            a = log["args"]
            out.append({"type": "minted", "block": log["blockNumber"], "tx": log["transactionHash"].hex(),
                        "projectId": int(a["projectId"]), "account": a["developer"], "amount": int(a["tonnes"])})
        for log in ev.Retired().get_logs(from_block=start):
            a = log["args"]
            out.append({"type": "retired", "block": log["blockNumber"], "tx": log["transactionHash"].hex(),
                        "projectId": int(a["projectId"]), "account": a["account"], "amount": int(a["amount"]),
                        "beneficiary": a["beneficiary"], "reason": a["reason"]})
        for log in ev.ProjectRevoked().get_logs(from_block=start):
            a = log["args"]
            out.append({"type": "revoked", "block": log["blockNumber"], "tx": log["transactionHash"].hex(),
                        "projectId": int(a["projectId"]), "reason": a["reason"]})
        out.sort(key=lambda e: e["block"], reverse=True)
        return out[:limit]
