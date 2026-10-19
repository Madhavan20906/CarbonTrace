# CarbonTrace

**Carbon credits that are checked against satellite evidence before they exist, and cannot be counted twice.**

Built for the IEEE ClimateChain Global Hackathon 2026, track **Carbon Markets & Emissions Transparency**.

Carbon markets lose credibility in two places. A claim can be false (a forest that is not there, or was cut down), and
a true claim can be sold more than once. Most blockchain carbon projects only record credits after the fact, so they
inherit the first problem. CarbonTrace fixes both before a credit is minted:

1. **Verify.** An AI verifier turns the claimed polygon into satellite evidence (monthly NDVI), scores it with a fixed,
   re-runnable formula, and signs an EIP-712 attestation only if the claim holds up. Inflated claims are trimmed to what the land can hold.
2. **Lock.** The registry contract checks the verifier's signature and claims every land cell for that year. A second claim over the same land reverts on-chain.
3. **Trace.** Each credit links to a content-addressed evidence bundle. Your browser re-hashes it and compares with the hash stored on-chain.
4. **Retire.** Retiring burns the credit and publishes who retired it and why. Revoked projects freeze and release their land.

## Quick start (local, about 5 minutes)

Needs Node 20+ and Python 3.11+.

```bash
make install          # contracts, backend venv, frontend
make test             # 27 contract tests, 50 backend tests, 8 frontend tests
make e2e              # real chain + real API + the full fraud walkthrough
```

Run it for real, in four terminals:

```bash
make chain            # 1. local blockchain
make deploy           # 2. deploy the registry (writes deployments/localhost.json)
make api              # 3. verifier API on :8000
make web              # 4. app on http://localhost:5173
```

Open the app and go to **Fraud lab**, then **Run all cases**. Restart `make chain` and `make deploy` to reset the demo.
Or run everything with `docker compose up --build` and open http://localhost:8080 (see "What is verified" below).

## What happens in the fraud lab

| Case | Verifier | Contract |
|---|---|---|
| Rainforest restoration, Western Ghats | Approved, 98/100 | Issues 700 t |
| Same land claimed by a second developer | Approved (the forest is real) | **Refuses: land already claimed** |
| "Forest" in the Thar Desert | Rejected | Nothing to mint |
| "Urban forest" in central Chennai | Rejected | Nothing to mint |
| Forest cleared mid-year | Rejected: clearing detected | Nothing to mint |
| Real forest, claim about twice capacity | Approved, trimmed to capacity | Issues 802 t instead of 1,500 t |
| Conifer reforestation, Oregon | Approved | Issues 700 t |

## Repository layout

```
contracts-pkg/   Solidity registry, Hardhat tests, deploy script
backend/         FastAPI verifier: geometry, satellite evidence, scoring, EIP-712 signing, chain reader
frontend/        React + TypeScript app: registry, verify, fraud lab, project pages
scripts/e2e.sh   self-contained end-to-end run
docs/            architecture, threat model, deployment, demo script, Devpost text
```

## What is verified, and what is not

Stated plainly so nothing is oversold:

- **Tested and passing:** the contract (27 tests), scoring and geometry (50 backend tests), EIP-712 interoperability between the
  Python signer and the Solidity verifier on a live local chain (`make e2e`), frontend type-check, unit tests, server-render smoke tests and production build.
- **Default evidence is simulated.** Out of the box the satellite step uses a deterministic biome reference table so the demo works offline.
  It is labelled `simulated` in every API response, evidence bundle and screen. It is not satellite data.
- **Live Sentinel-2 mode is implemented but not exercised against the network in the build environment.** Its NDVI math and STAC request are unit tested;
  the COG reading path needs a machine with internet and GDAL. Try it with `pip install -r backend/requirements-live.txt` and `SATELLITE_PROVIDER=sentinel2`.
- **The UI has been type-checked, built and render-tested, but not clicked through in a browser by the author of this code.** Do one full pass before recording the demo.
- **Docker files are untested.** The local `make` flow is the verified path.
- **Sequestration rates are conservative placeholders**, not a certified methodology. Real issuance would implement an approved one (for example Verra VM0047).
- **Not audited.** Do not use with real funds.

See `docs/THREAT_MODEL.md` for trust assumptions and `docs/DEPLOY.md` for putting it on Polygon Amoy or Sepolia.

## License

MIT
"# CarbonTrace" 
