import { AppProvider, useApp, useRoute } from "./state";
import { DEMO_LABELS, demoAvailable, type WalletMode } from "./chain";
import { shortAddr } from "./format";
import FraudLab from "./pages/FraudLab";
import Project from "./pages/Project";
import Registry from "./pages/Registry";
import Verify from "./pages/Verify";

function WalletPicker() {
  const { cfg, mode, setMode, address, signer } = useApp();
  if (!cfg) return null;
  const modes: WalletMode[] = demoAvailable(cfg) ? ["demo-a", "demo-b", "demo-buyer", "browser"] : ["browser"];
  return (
    <div className="wallet">
      <label className="sr" htmlFor="wallet-mode">Wallet</label>
      <select id="wallet-mode" value={mode} onChange={(e) => setMode(e.target.value as WalletMode)}>
        {modes.map((m) => <option key={m} value={m}>{DEMO_LABELS[m]}</option>)}
      </select>
      {address ? <code title={address}>{shortAddr(address)}</code>
        : mode === "browser" && <button className="btn small" onClick={() => void signer().catch(() => undefined)}>Connect</button>}
    </div>
  );
}

function Shell() {
  const { cfg, cfgError } = useApp();
  const route = useRoute();
  const [page, arg] = route;
  const link = (hash: string, label: string, active: boolean) => (
    <a href={hash} aria-current={active ? "page" : undefined}>{label}</a>
  );

  return (
    <>
      <header className="top">
        <a className="brand" href="#/">CarbonTrace</a>
        <nav aria-label="Main">
          {link("#/", "Registry", !page)}
          {link("#/verify", "Verify a project", page === "verify")}
          {link("#/lab", "Fraud lab", page === "lab")}
        </nav>
        <WalletPicker />
      </header>
      <main>
        {cfgError && (
          <div className="notice err" role="alert">
            <b>The verifier is not reachable.</b> {cfgError} Start it with <code>uvicorn app.main:app</code> in the backend folder, then reload.
          </div>
        )}
        {!page && <Registry />}
        {page === "verify" && <Verify />}
        {page === "lab" && <FraudLab />}
        {page === "project" && arg && <Project key={arg} id={Number(arg)} />}
      </main>
      <footer>
        {cfg ? (
          <>
            <span>Registry <code title={cfg.address}>{shortAddr(cfg.address)}</code> on {cfg.network} (chain {cfg.chainId})</span>
            <span>{cfg.simulated ? "Evidence source: demo reference data" : "Evidence source: Sentinel-2 imagery"}</span>
            <span>Scoring model {cfg.model}</span>
          </>
        ) : <span>Connecting…</span>}
      </footer>
    </>
  );
}

export default function App() {
  return <AppProvider><Shell /></AppProvider>;
}
