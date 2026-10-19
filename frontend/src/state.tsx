import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Signer } from "ethers";
import { api, type Config } from "./api";
import { demoAvailable, getSigner, type WalletMode } from "./chain";

interface AppState {
  cfg: Config | null;
  cfgError: string | null;
  mode: WalletMode;
  setMode: (m: WalletMode) => void;
  address: string | null;
  /** Returns a signer for the selected wallet, connecting it if needed. */
  signer: () => Promise<Signer>;
}

const Ctx = createContext<AppState | null>(null);
export const useApp = () => {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside provider");
  return v;
};

export function AppProvider({ children }: { children: ReactNode }) {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [cfgError, setCfgError] = useState<string | null>(null);
  const [mode, setModeState] = useState<WalletMode>("browser");
  const [address, setAddress] = useState<string | null>(null);

  useEffect(() => {
    api.config().then((c) => {
      setCfg(c);
      if (demoAvailable(c)) setModeState("demo-a");
    }).catch((e: Error) => setCfgError(e.message));
  }, []);

  useEffect(() => {
    setAddress(null);
    if (!cfg || mode === "browser") return;
    getSigner(mode, cfg).then((s) => s.getAddress()).then(setAddress).catch(() => setAddress(null));
  }, [cfg, mode]);

  const signer = useCallback(async () => {
    if (!cfg) throw new Error("The verifier API is not reachable yet.");
    const s = await getSigner(mode, cfg);
    setAddress(await s.getAddress());
    return s;
  }, [cfg, mode]);

  const value = useMemo<AppState>(
    () => ({ cfg, cfgError, mode, setMode: setModeState, address, signer }),
    [cfg, cfgError, mode, address, signer],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** Tiny hash router: "#/", "#/verify", "#/lab", "#/project/3". */
export function useRoute(): string[] {
  const parse = () => window.location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const [route, setRoute] = useState<string[]>(parse());
  useEffect(() => {
    const on = () => setRoute(parse());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}
