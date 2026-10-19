import { useEffect, useState } from "react";
import { Interface } from "ethers";
import abi from "../abi.json";
import { api, type Scenario, type VerifyResponse } from "../api";
import { useApp } from "../state";
import { demoAvailable, explainError, getSigner, mintFromAttestation, type WalletMode } from "../chain";
import MapView from "../components/MapView";
import { tonnes } from "../format";

const iface = new Interface(abi);

interface Outcome {
  running: boolean;
  ai?: VerifyResponse;
  chain?: { ok: boolean; message: string; projectId?: number | null };
  error?: string;
}

const EXPECT_LABEL: Record<Scenario["expect"], string> = {
  approved: "Should be issued",
  "approved-trimmed": "Should be issued, trimmed",
  rejected: "Should be rejected by the verifier",
  "chain-rejects": "Should be rejected by the contract",
};

export default function FraudLab() {
  const { cfg } = useApp();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [out, setOut] = useState<Record<string, Outcome>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [runningAll, setRunningAll] = useState(false);
  const canMint = !!cfg && demoAvailable(cfg);

  useEffect(() => { api.scenarios().then(setScenarios).catch(() => setScenarios([])); }, []);

  const patch = (id: string, o: Partial<Outcome>) => setOut((prev) => ({ ...prev, [id]: { ...prev[id], running: false, ...o } }));

  const run = async (s: Scenario) => {
    if (!cfg) return;
    setSelected(s.id);
    patch(s.id, { running: true, ai: undefined, chain: undefined, error: undefined });
    try {
      // Two different developers, so the duplicate claim really comes from a second party.
      const mode: WalletMode = s.id === "double-count" ? "demo-b" : "demo-a";
      const wallet = canMint ? await getSigner(mode, cfg) : null;
      const developer = wallet ? await wallet.getAddress() : "0x70997970C51812dc3A010C7d01b50e0d17dc79C8";
      const ai = await api.verify({ ...s.request, developer });
      patch(s.id, { ai });
      if (ai.signed && ai.attestation && wallet) {
        try {
          const res = await mintFromAttestation(cfg, wallet, ai.attestation);
          patch(s.id, { ai, chain: { ok: true, message: `Issued ${tonnes(ai.verifiedTonnes)} on-chain.`, projectId: res.projectId } });
        } catch (e) {
          patch(s.id, { ai, chain: { ok: false, message: explainError(e, iface) } });
        }
      }
    } catch (e) {
      patch(s.id, { error: (e as Error).message });
    }
  };

  const runAll = async () => {
    setRunningAll(true);
    for (const s of scenarios) await run(s);
    setRunningAll(false);
  };

  const sel = scenarios.find((s) => s.id === selected);
  const selOut = selected ? out[selected] : undefined;

  return (
    <>
      <h1 className="page-title">Fraud lab</h1>
      <p className="lede narrow">
        Seven claims, from honest to dishonest. Each one goes to the verifier, and anything it signs is sent to the registry contract.
        Run them in order: the second case only fails because the first one already locked the land.
      </p>
      <div className="cta-row">
        <button className="btn primary" onClick={() => void runAll()} disabled={runningAll || !cfg || !scenarios.length}>{runningAll ? "Running all cases…" : "Run all cases"}</button>
        {cfg && !canMint && <span className="notice warn inline">Demo wallets only exist on the local chain, so only the verifier step will run here. Use Verify a project with your own wallet for the on-chain step.</span>}
      </div>

      <ol className="cases">
        {scenarios.map((s) => {
          const o = out[s.id];
          return (
            <li key={s.id} className={`case${selected === s.id ? " active" : ""}`}>
              <div className="case-main">
                <h2>{s.title}</h2>
                <p>{s.story}</p>
                <p className="muted small">{EXPECT_LABEL[s.expect]}. Claims {tonnes(s.request.claimed_tonnes)}.</p>
              </div>
              <div className="case-result" aria-live="polite">
                {!o && <span className="muted">Not run yet</span>}
                {o?.running && <span className="muted">Running…</span>}
                {o?.error && <span className="tag bad">{o.error}</span>}
                {o?.ai && (
                  <ul className="stages">
                    <li><span className={`tag ${o.ai.approved ? "good" : "bad"}`}>{o.ai.approved ? "Verifier: approved" : "Verifier: rejected"}</span> score {o.ai.score}</li>
                    {o.ai.approved && o.ai.verifiedTonnes < o.ai.claimedTonnes && <li className="muted small">Trimmed {tonnes(o.ai.claimedTonnes)} to {tonnes(o.ai.verifiedTonnes)}</li>}
                    {o.chain && (
                      <li>
                        <span className={`tag ${o.chain.ok ? "good" : "bad"}`}>{o.chain.ok ? "Contract: issued" : "Contract: refused"}</span>
                        <span className="small"> {o.chain.message}</span>
                        {o.chain.ok && o.chain.projectId ? <> <a href={`#/project/${o.chain.projectId}`}>View</a></> : null}
                      </li>
                    )}
                    {!o.ai.approved && <li className="muted small">{o.ai.checks.filter((c) => c.status === "fail").map((c) => c.label).join(", ")}</li>}
                  </ul>
                )}
              </div>
              <button className="btn small" onClick={() => void run(s)} disabled={o?.running || runningAll || !cfg}>Run this case</button>
            </li>
          );
        })}
      </ol>

      {sel && selOut?.ai && (
        <section className="lab-detail">
          <h2>{sel.title}</h2>
          <MapView polygons={[{ id: sel.id, ring: selOut.ai.geometry.ring, color: selOut.ai.approved ? "#3fae6a" : "#d64545" }]} height={300} label={`Map of ${sel.title}`} />
          <p className="verdict-text">{selOut.ai.explanation}</p>
        </section>
      )}
    </>
  );
}
