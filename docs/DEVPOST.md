# Devpost submission text (copy, then edit the bracketed parts)

## Track alignment
**Carbon Markets & Emissions Transparency.** CarbonTrace answers the track's challenge (trust, transparency and efficiency in carbon markets)
with three of the four listed builds: blockchain-based carbon credit verification, smart contracts that prevent double counting,
and a transparent registry anyone can audit.

## Tagline
Carbon credits that are checked against satellite evidence before they exist, and cannot be counted twice.

## The problem
Carbon credits only mean something if the climate benefit is real and sold once. Today a claim can be false, and a true claim can be sold to several buyers.
Blockchain registries record credits well, but they trust whatever is written into them, so they cannot tell a forest from a car park.

## What it does
A project developer outlines their land and claims a number of tonnes. An AI verifier pulls monthly vegetation evidence for that land,
scores it with a fixed formula, and signs an attestation only when the claim holds up. It cuts inflated claims down to what the land can hold.
The registry smart contract then checks the signature and locks every land cell for that year. A second claim over the same land is refused by the contract itself.
Every credit links to its evidence, and the app re-hashes that evidence in the browser to prove it matches what is on-chain.
Buyers retire credits with a named beneficiary and reason, and the credits are burned.

## How we built it
- Solidity ERC-1155 registry with EIP-712 attestations, grid-cell double-count guard, retirement, revocation, pause and verifier rotation. 27 tests.
- FastAPI verifier: geometry and grid rasterisation, satellite evidence providers, deterministic scoring, EIP-712 signing in Python. 50 tests.
- React and TypeScript app with a map drawing tool, evidence ribbon, fraud lab and project pages.
- An end-to-end script proves a Python-signed attestation is accepted by the Solidity contract on a live chain.

## Why the AI is trustworthy here
The decision is a transparent scoring formula over published evidence, so anyone can re-run it. A language model only writes the explanation, and cannot change the verdict.
[If used: Explanations by Claude.]

## Impact and scale
Users: registries and verifiers (issue with confidence), developers (prove claims quickly), buyers and auditors (trace any credit to the land).
It scales by swapping in finer imagery and approved methodologies, adding more independent verifiers behind a threshold signature, and deploying on a low-cost L2.
Adoption path: it can sit in front of an existing registry as a pre-issuance check, since the verifier and uniqueness gate are separate pieces.

## Honest limits
Demo evidence is simulated by default and labelled as such; a live Sentinel-2 mode is included. Sequestration rates are placeholders for a certified methodology.
The verifier is a single trusted signer today (threshold signing is the next step). Not audited.

## Built with
Solidity, Hardhat, OpenZeppelin, Python, FastAPI, Shapely, web3.py, React, TypeScript, ethers, Leaflet, Sentinel-2 / Earth Search STAC.

## Links to fill in
- Repo: [GitHub URL]
- Demo video: [URL]
- Live app: [URL] / Testnet contract: [explorer URL]
