# Threat model and known limits

## What the system guarantees
- A credit exists only if an address with `VERIFIER_ROLE` signed it. Tampering with tonnes, cells, URI or recipient invalidates the signature (tested).
- The same land cell cannot back two active projects in one vintage year (tested, including partial overlap).
- Attestations expire, can be used once (nonce), and must be submitted by the recipient wallet.
- Retired credits are burned. Revoked credits are frozen. Pausing freezes all movement.
- The evidence behind any credit can be re-hashed and compared with the on-chain hash.

## What it does NOT guarantee
| Risk | Status | Mitigation path |
|---|---|---|
| The verifier key is compromised or the verifier is dishonest | **Single point of trust.** The contract cannot tell a bad signature from a good one. | Threshold signatures from several independent verifiers, a KMS/HSM, and role rotation (rotation already works). Revocation lets governance undo past issuance. |
| Developer submits a polygon that is not theirs | Not detected. The system proves the forest exists and is unclaimed here, not who owns it. | Land-title or registry attestation as a second signed input. |
| Overlap smaller than the grid | A cell is claimed if 20% covered, so tiny overlaps inside one cell can slip past. | Finer grid, or exact-overlap check in the verifier using a registry index. |
| Same land, different developer, different grid alignment | Cells are global, so alignment is shared. Not an issue. | n/a |
| Simulated evidence | The default demo mode. It is labelled everywhere. | Use `SATELLITE_PROVIDER=sentinel2`. |
| NDVI cannot prove additionality, permanence or leakage | Out of scope. Real credits need an approved methodology. | Implement a Verra or Gold Standard methodology on top of the evidence pipeline. |
| Front-running | Harmless: the mint always goes to the attested recipient, and only the recipient may submit. | n/a |
| Contract bugs | Not audited. | Independent audit before any real value. |
| Admin keys | One admin holds admin, revoker and pauser roles by default. | Move to a multisig with timelock (`ADMIN_ADDRESS`). |
| API abuse | No rate limiting or authentication on `/api/verify`. | Add rate limits and API keys before exposing publicly. |
