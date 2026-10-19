import { useEffect, useMemo, useState } from "react";
import { Interface } from "ethers";
import abi from "../abi.json";
import { api, type Scenario, type VerifyResponse } from "../api";
import { useApp } from "../state";
import { explainError, mintFromAttestation } from "../chain";
import MapView, { type Draft, type MapPolygon } from "../components/MapView";
import Report from "../components/Report";
import { tonnes } from "../format";

const iface = new Interface(abi);

type MintState =
  | { kind: "idle" }
  | { kind: "pending" }
  | { kind: "done"; projectId: number | null; hash: string }
  | { kind: "failed"; message: string };

export default function Verify() {
  const { cfg, signer, address } = useApp();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [name, setName] = useState("");
  const [vintage, setVintage] = useState(2025);
  const [claimed, setClaimed] = useState(500);
  const [type, setType] = useState<"reforestation" | "conservation">("reforestation");
  const [points, setPoints] = useState<[number, number][]>([]);
  const [drawing, setDrawing] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [mint, setMint] = useState<MintState>({ kind: "idle" });

  useEffect(() => { api.scenarios().then(setScenarios).catch(() => setScenarios([])); }, []);

  const edit = (next: [number, number][]) => { setPoints(next); setResult(null); setMint({ kind: "idle" }); setError(null); };

  const load = (s: Scenario) => {
    const ring = s.request.polygon as unknown as number[][];
    setName(s.request.name); setVintage(s.request.vintage); setClaimed(s.request.claimed_tonnes); setType(s.request.project_type);
    setPoints(ring.slice(0, -1).map((p) => [p[0], p[1]] as [number, number]));
    setDrawing(false); setResult(null); setMint({ kind: "idle" }); setError(null);
  };

  const draft = useMemo<Draft>(() => ({ points, enabled: drawing, onAdd: (p) => edit([...points, p]) }), [points, drawing]); // eslint-disable-line react-hooks/exhaustive-deps
  const polygons = useMemo<MapPolygon[]>(
    () => (result ? [{ id: "result", ring: result.geometry.ring, color: result.approved ? "#3fae6a" : "#d64545" }] : []),
    [result],
  );

  const canVerify = name.trim().length >= 3 && points.length >= 3 && claimed > 0 && !busy;

  const run = async () => {
    setBusy(true); setError(null); setResult(null); setMint({ kind: "idle" });
    try {
      const developer = await (await signer()).getAddress();
      const ring = [...points, points[0]];
      setResult(await api.verify({ name: name.trim(), developer, vintage, polygon: ring, claimed_tonnes: claimed, project_type: type }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const doMint = async () => {
    if (!cfg || !result?.attestation) return;
    setMint({ kind: "pending" });
    try {
      const out = await mintFromAttestation(cfg, await signer(), result.attestation);
      setMint({ kind: "done", projectId: out.projectId, hash: out.hash });
    } catch (e) {
      setMint({ kind: "failed", message: explainError(e, iface) });
    }
  };

  return (
    <>
      <h1 className="page-title">Verify a project</h1>
      <p className="lede narrow">Outline the land on the map, say how many tonnes you are claiming, and the verifier will check the claim against satellite evidence.</p>

      {scenarios.length > 0 && (
        <div className="presets" role="group" aria-label="Example projects">
          <span className="muted">Start from an example:</span>
          {scenarios.map((s) => <button key={s.id} className="chip" onClick={() => load(s)} title={s.story}>{s.title}</button>)}
        </div>
      )}

      <div className="workbench">
        <div>
          <MapView polygons={polygons} draft={draft} height={460} fit={!drawing || !!result}
            label="Map for outlining the project land. Click to place corners." />
          <div className="map-tools">
            <button className="btn small" onClick={() => setDrawing((d) => !d)}>{drawing ? "Stop drawing" : "Draw on map"}</button>
            <button className="btn small" disabled={!points.length} onClick={() => edit(points.slice(0, -1))}>Undo last corner</button>
            <button className="btn small" disabled={!points.length} onClick={() => edit([])}>Clear</button>
            <span className="muted small">
              {points.length < 3 ? `Click the map to place corners (${points.length} so far, need 3).` : `${points.length} corners placed.`}
            </span>
          </div>
        </div>

        <form className="panel" onSubmit={(e) => { e.preventDefault(); if (canVerify) void run(); }}>
          <label>Project name
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Highland Forest Restoration" />
          </label>
          <div className="row">
            <label>Year of the credits
              <input type="number" min={2015} max={new Date().getFullYear()} value={vintage} onChange={(e) => { setVintage(Number(e.target.value)); setResult(null); }} />
            </label>
            <label>Tonnes of CO₂ claimed
              <input type="number" min={1} value={claimed} onChange={(e) => { setClaimed(Number(e.target.value)); setResult(null); }} />
            </label>
          </div>
          <label>Project type
            <select value={type} onChange={(e) => setType(e.target.value as typeof type)}>
              <option value="reforestation">Reforestation</option>
              <option value="conservation">Conservation of existing forest</option>
            </select>
          </label>
          <p className="muted small">Credits will be issued to {address ?? "the wallet you connect"}.</p>
          <button className="btn primary wide" type="submit" disabled={!canVerify}>{busy ? "Checking satellite evidence…" : "Check this claim"}</button>
          {error && <p className="notice err" role="alert">{error}</p>}
        </form>
      </div>

      {result && (
        <>
          <Report
            approved={result.approved} score={result.score} claimed={result.claimedTonnes} verified={result.verifiedTonnes}
            capacity={result.capacityTonnes} areaHa={result.geometry.areaHa} cells={result.geometry.cells}
            explanation={result.explanation} explanationBy={result.explanationBy} checks={result.checks}
            observations={result.satellite.observations} simulated={result.simulated} biome={result.satellite.biome}
          />

          {result.chainConflict && (
            <p className="notice warn">
              This land already backs <a href={`#/project/${result.chainConflict.projectId}`}>project #{result.chainConflict.projectId}</a> for {vintage}.
              {result.signed ? " The verifier signed because the imagery is genuine, but the registry contract will refuse to mint it twice." : ""}
            </p>
          )}

          {result.signed && result.attestation && (
            <section className="mint">
              <div>
                <h3>Issue {tonnes(result.verifiedTonnes)} on-chain</h3>
                <p className="muted small">Sends the verifier's signed attestation to the registry contract. The contract re-checks the signature and that the land is unclaimed.</p>
              </div>
              <button className="btn primary" onClick={() => void doMint()} disabled={mint.kind === "pending" || mint.kind === "done"}>
                {mint.kind === "pending" ? "Waiting for the chain…" : `Issue ${tonnes(result.verifiedTonnes)}`}
              </button>
            </section>
          )}
          {mint.kind === "done" && (
            <p className="notice ok" role="status">
              Credits issued{mint.projectId ? <> as <a href={`#/project/${mint.projectId}`}>project #{mint.projectId}</a></> : ""}. Transaction {mint.hash.slice(0, 12)}…
            </p>
          )}
          {mint.kind === "failed" && <p className="notice err" role="alert">{mint.message}</p>}
          {!result.signed && !result.approved && <p className="notice err">No attestation was issued, so nothing can be minted for this claim.</p>}
        </>
      )}
    </>
  );
}
