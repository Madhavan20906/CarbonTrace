export type Status = "pass" | "warn" | "fail";

export interface Check { id: string; label: string; status: Status; value: string; detail: string }
export interface Observation {
  month: number; mean_ndvi: number; p10: number; p90: number;
  canopy_fraction: number; valid_fraction: number; scene_id: string | null;
}
export interface Attestation {
  message: Record<string, string | number>;
  signature: string; signer: string; cells: string[]; metadataURI: string;
}
export interface VerifyRequest {
  name: string; developer: string; vintage: number; polygon: number[][];
  claimed_tonnes: number; project_type: "reforestation" | "conservation";
}
export interface VerifyResponse {
  approved: boolean; score: number; verifiedTonnes: number; capacityTonnes: number; claimedTonnes: number;
  checks: Check[]; metrics: Record<string, number | null>; components: Record<string, unknown>;
  capsApplied: string[]; explanation: string; explanationBy: string; modelVersion: string; simulated: boolean;
  satellite: { provider: string; biome: string; observations: Observation[]; notes: string[]; lowConfidence: boolean };
  geometry: { ring: number[][]; areaHa: number; cells: number; centroid: [number, number] };
  evidenceHash: string; chainConflict: { cell: number; projectId: number } | null;
  signed: boolean; attestation: Attestation | null;
}
export interface ProjectRow {
  id: number; developer: string; vintage: number; scoreBps: number; revoked: boolean; lat: number; lon: number;
  cellCount: number; mintedAt: number; tonnes: number; retired: number; evidenceHash: string; metadataURI: string;
}
export interface EvidenceBundle {
  schema: string; createdAt: string;
  project: { name: string; developer: string; vintage: number; type: string; claimedTonnes: number };
  geometry: { ring: number[][]; areaHa: number; centroid: [number, number]; cells: number[] };
  satellite: VerifyResponse["satellite"] & { simulated: boolean };
  assessment: { score: number; verified_tonnes: number; claimed_tonnes: number; capacity_tonnes: number; checks: Check[]; metrics: Record<string, number | null> };
  explanation: { text: string; author: string };
}
export interface Scenario {
  id: string; title: string; story: string;
  expect: "approved" | "chain-rejects" | "rejected" | "approved-trimmed";
  request: Omit<VerifyRequest, "developer">;
}
export interface Config {
  chainId: number; address: string; network: string; rpcUrl: string; deployBlock: number;
  satelliteProvider: string; simulated: boolean; approveThreshold: number; verifierSigner: string;
  model: string; llmExplanations: boolean;
}
export interface Stats { projects: number; minted: number; retired: number; revoked: number; outstanding: number }
export interface Activity {
  type: "minted" | "retired" | "revoked"; block: number; tx: string; projectId: number;
  account?: string; amount?: number; beneficiary?: string; reason?: string;
}

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

export class ApiError extends Error {}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg ?? "invalid"}`).join("; ");
  }
  return "Request failed.";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, init);
  } catch {
    throw new ApiError("Cannot reach the verifier API. Check that the backend is running.");
  }
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try { detail = (await res.json()).detail; } catch { /* keep status text */ }
    throw new ApiError(describe(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  config: () => request<Config>("/api/config"),
  scenarios: () => request<Scenario[]>("/api/scenarios"),
  stats: () => request<Stats>("/api/stats"),
  projects: () => request<ProjectRow[]>("/api/projects"),
  project: (id: number) => request<ProjectRow>(`/api/projects/${id}`),
  activity: () => request<Activity[]>("/api/activity"),
  /** Exact bytes of the evidence bundle, so the browser can re-hash them against the on-chain hash. */
  evidenceRaw: async (hash: string): Promise<string> => {
    let res: Response;
    try { res = await fetch(`${BASE}/api/evidence/${hash}`); } catch { throw new ApiError("Cannot reach the verifier API."); }
    if (!res.ok) throw new ApiError("Evidence bundle not found.");
    return res.text();
  },
  verify: (body: VerifyRequest) =>
    request<VerifyResponse>("/api/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
};
