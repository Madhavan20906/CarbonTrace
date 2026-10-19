import { useCallback, useEffect, useMemo, useState } from "react";
import { Interface, keccak256, toUtf8Bytes } from "ethers";
import abi from "../abi.json";
import { api, type EvidenceBundle, type ProjectRow } from "../api";
import { useApp } from "../state";
import { balanceOf, explainError, retireCredits, transferCredits } from "../chain";
import MapView from "../components/MapView";
import Report from "../components/Report";
import { date, shortAddr, tonnes } from "../format";

const iface = new Interface(abi);

type Integrity = { state: "checking" } | { state: "ok" } | { state: "bad" } | { state: "unavailable" };

export default function Project({ id }: { id: number }) {
  const { cfg, mode, signer } = useApp();
  const [project, setProject] = useState<ProjectRow | null>(null);
  const [bundle, setBundle] = useState<EvidenceBundle | null>(null);
  const [integrity, setIntegrity] = useState<Integrity>({ state: "checking" });
  const [error, setError] = useState<string | null>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [amount, setAmount] = useState(1);
  const [beneficiary, setBeneficiary] = useState("");
  const [reason, setReason] = useState("");
  const [to, setTo] = useState("");

  const load = useCallback(async () => {
    try {
      const p = await api.project(id);
      setProject(p);
      setIntegrity({ state: "checking" });
      try {
        const raw = await api.evidenceRaw(p.evidenceHash);
        setBundle(JSON.parse(raw) as EvidenceBundle);
        // Re-hash the exact bytes in the browser and compare with the hash stored on-chain.
        setIntegrity({ state: keccak256(toUtf8Bytes(raw)) === p.evidenceHash ? "ok" : "bad" });
      } catch {
        setIntegrity({ state: "unavailable" });
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    // Demo wallets need no prompt, so show their balance straight away. A browser wallet is only queried on request.
    if (!cfg || mode === "browser") { setBalance(null); return; }
    signer().then((s) => balanceOf(cfg, s, id)).then(setBalance).catch(() => setBalance(null));
  }, [cfg, mode, signer, id, project?.retired]);

  const act = async (fn: () => Promise<string>, done: string) => {
    setBusy(true); setMsg(null);
    try {
      await fn();
      setMsg({ kind: "ok", text: done });
      await load();
      if (cfg) setBalance(await balanceOf(cfg, await signer(), id));
    } catch (e) {
      setMsg({ kind: "err", text: explainError(e, iface) });
    } finally {
      setBusy(false);
    }
  };

  const polygons = useMemo(
    () => (bundle ? [{ id: "site", ring: bundle.geometry.ring, color: project?.revoked ? "#d64545" : "#3fae6a" }] : []),
    [bundle, project?.revoked],
  );

  if (error) return <p className="notice err">{error} <a href="#/">Back to the registry</a></p>;
  if (!project) return <p className="muted">Loading project…</p>;

  const available = project.tonnes - project.retired;

  return (
    <>
      <p className="crumb"><a href="#/">Registry</a> / Project #{project.id}</p>
      <h1 className="page-title">{bundle?.project.name ?? `Project #${project.id}`}</h1>
      {project.revoked && <p className="notice err" role="alert">This project was revoked. Its credits are frozen and can no longer be moved or retired.</p>}

      <div className="split wide-left">
        <div>
          {bundle && <MapView polygons={polygons} height={340} label="Map of the project site" />}
          <dl className="facts onchain">
            <div><dt>Credits issued</dt><dd>{tonnes(project.tonnes)}</dd></div>
            <div><dt>Retired</dt><dd>{tonnes(project.retired)}</dd></div>
            <div><dt>{project.revoked ? "Frozen" : "Still available"}</dt><dd>{tonnes(available)}</dd></div>
            <div><dt>Credit year</dt><dd>{project.vintage}</dd></div>
            <div><dt>Issued on</dt><dd>{date(project.mintedAt)}</dd></div>
            <div><dt>Developer</dt><dd title={project.developer}>{shortAddr(project.developer)}</dd></div>
            <div><dt>Land locked</dt><dd>{project.cellCount} grid cells</dd></div>
          </dl>
          <div className={`integrity ${integrity.state}`} role="status">
            {integrity.state === "checking" && "Checking the evidence against the on-chain hash…"}
            {integrity.state === "ok" && <>Evidence verified. Your browser re-computed the hash of the report below and it matches the one stored on-chain: <code>{project.evidenceHash}</code></>}
            {integrity.state === "bad" && "Warning: the evidence bundle does not match the hash recorded on-chain. Do not trust this report."}
            {integrity.state === "unavailable" && "The evidence bundle could not be loaded from the verifier."}
          </div>
        </div>

        <aside className="panel">
          <h2>Use these credits</h2>
          {mode === "browser" && balance === null && (
            <button className="btn small" onClick={() => cfg && void signer().then((s) => balanceOf(cfg, s, id)).then(setBalance).catch((e) => setMsg({ kind: "err", text: explainError(e) }))}>Connect wallet to see balance</button>
          )}
          {balance !== null && <p>Your balance: <b>{tonnes(balance)}</b></p>}

          <form onSubmit={(e) => { e.preventDefault(); if (cfg) void act(async () => retireCredits(cfg, await signer(), id, amount, beneficiary, reason), `Retired ${tonnes(amount)}. They are burned for good.`); }}>
            <h3>Retire (use them up)</h3>
            <label>Tonnes<input type="number" min={1} value={amount} onChange={(e) => setAmount(Number(e.target.value))} /></label>
            <label>Retired on behalf of<input value={beneficiary} onChange={(e) => setBeneficiary(e.target.value)} placeholder="Company or person" maxLength={80} /></label>
            <label>Reason<input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="FY2026 flight emissions" maxLength={120} /></label>
            <button className="btn primary wide" disabled={busy || project.revoked || amount < 1}>Retire {tonnes(amount || 0)}</button>
          </form>

          <form onSubmit={(e) => { e.preventDefault(); if (cfg) void act(async () => transferCredits(cfg, await signer(), id, to.trim(), amount), `Sent ${tonnes(amount)} to ${shortAddr(to.trim())}.`); }}>
            <h3>Send to another wallet</h3>
            <label>Wallet address<input value={to} onChange={(e) => setTo(e.target.value)} placeholder="0x…" spellCheck={false} /></label>
            <button className="btn wide" disabled={busy || project.revoked || amount < 1 || !/^0x[0-9a-fA-F]{40}$/.test(to.trim())}>Send {tonnes(amount || 0)}</button>
          </form>
          {msg && <p className={`notice ${msg.kind}`} role={msg.kind === "err" ? "alert" : "status"}>{msg.text}</p>}
        </aside>
      </div>

      {bundle && (
        <Report
          approved score={bundle.assessment.score} claimed={bundle.assessment.claimed_tonnes} verified={bundle.assessment.verified_tonnes}
          capacity={bundle.assessment.capacity_tonnes} areaHa={bundle.geometry.areaHa} cells={bundle.geometry.cells.length}
          explanation={bundle.explanation.text} explanationBy={bundle.explanation.author} checks={bundle.assessment.checks}
          observations={bundle.satellite.observations} simulated={bundle.satellite.simulated} biome={bundle.satellite.biome}
        />
      )}
    </>
  );
}
