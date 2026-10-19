import type { Check, Observation } from "../api";
import { tonnes } from "../format";
import Checks from "./Checks";
import EvidenceRibbon from "./EvidenceRibbon";

interface Props {
  approved: boolean; score: number; claimed: number; verified: number; capacity: number;
  areaHa: number; cells: number; explanation: string; explanationBy: string;
  checks: Check[]; observations: Observation[]; simulated: boolean; biome: string;
}

/** The verification report: verdict, plain-language reason, satellite evidence and each check. */
export default function Report(p: Props) {
  const trimmed = p.approved && p.verified < p.claimed;
  return (
    <section className={`report ${p.approved ? "ok" : "no"}`} aria-live="polite">
      {p.simulated && (
        <p className="banner">
          Demo data: these NDVI values come from a biome reference table, not from satellite imagery. Start the verifier with
          <code> SATELLITE_PROVIDER=sentinel2 </code> to use real Sentinel-2 scenes.
        </p>
      )}
      <header className="verdict">
        <div className="verdict-word">{p.approved ? "Verified" : "Rejected"}</div>
        <div className="verdict-score" aria-label={`Score ${p.score} out of 100`}>
          <span className="score-num">{p.score}</span><span className="score-of">/100</span>
        </div>
        <p className="verdict-text">{p.explanation}</p>
      </header>

      <dl className="facts">
        <div><dt>Site</dt><dd>{p.areaHa.toLocaleString("en-US", { maximumFractionDigits: 1 })} ha, {p.cells} grid cells</dd></div>
        <div><dt>Land type</dt><dd>{p.biome}</dd></div>
        <div><dt>Claimed</dt><dd>{tonnes(p.claimed)}</dd></div>
        <div><dt>Land can hold</dt><dd>{tonnes(Math.round(p.capacity))}</dd></div>
        <div className="emph"><dt>Credits issued</dt><dd>{tonnes(p.verified)}{trimmed ? " (trimmed to capacity)" : ""}</dd></div>
      </dl>

      <h3>Satellite evidence</h3>
      <EvidenceRibbon observations={p.observations} />

      <h3>What the verifier checked</h3>
      <Checks checks={p.checks} />
      <p className="muted small">
        Decisions come from a fixed scoring formula that anyone can re-run on the published evidence.
        {p.explanationBy === "rules" ? " The explanation is generated from the same checks." : ` The explanation was written by ${p.explanationBy}; it cannot change the decision.`}
      </p>
    </section>
  );
}
