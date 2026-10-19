# 4-minute demo video script

Rehearse once end to end first. Reset with a fresh `make chain` and `make deploy`. Record at 1080p, browser zoom 110%.

| Time | On screen | Say |
|---|---|---|
| 0:00 | Registry page, empty | "Carbon credits have two problems: a claim can be false, and a true claim can be sold twice. CarbonTrace fixes both before a credit exists." |
| 0:20 | Verify page, load "Rainforest restoration, Western Ghats", click Check this claim | "A developer outlines land and claims 700 tonnes. The verifier pulls a year of vegetation data for exactly that polygon." |
| 0:45 | Scroll the report: evidence ribbon, checks | "Green all year, no clearing, claim within what the land can hold. Score 98. The score is a fixed formula, so anyone can re-run it." |
| 1:10 | Click Issue 700 t | "The contract checks the verifier's signature and locks every land cell for 2025." |
| 1:25 | Open the project page, point at the integrity banner | "My browser just re-hashed this evidence and it matches the hash on-chain. Change one byte and this turns red." |
| 1:50 | Fraud lab, Run all cases | "Now the villains." |
| 2:00 | Row 2: verifier approves, contract refuses | "Same land, second developer. The imagery is real, so the AI approves. The contract refuses: that land already backs project 1. The AI cannot see duplicates; the chain can." |
| 2:30 | Rows 3 to 5 | "A desert, a city, and a forest that was cut down in July. All rejected, no attestation, nothing to mint." |
| 2:55 | Row 6 | "A real forest with an inflated claim. Not rejected, trimmed: 1,500 tonnes claimed, 802 issued." |
| 3:15 | Project page, retire 120 t with beneficiary | "Buyers retire credits for a named company and reason. They are burned for good." |
| 3:35 | Registry page with totals and map | "Every credit traces to land on a map, with its evidence. Next: several independent verifiers, live Sentinel-2 imagery, and an approved methodology." |
| 3:50 | Title card with repo link | "CarbonTrace. Thank you." |

Say out loud once: "The default demo uses simulated vegetation data; live Sentinel-2 mode is included." Judges respect that.
