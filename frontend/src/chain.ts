import { BrowserProvider, Contract, JsonRpcProvider, Wallet, type Signer, type Interface } from "ethers";
import abi from "./abi.json";
import type { Attestation, Config } from "./api";

/** Hardhat's publicly known dev accounts. They only work on the local chain (31337) and hold no real value. */
const DEMO_KEYS = {
  "demo-a": "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
  "demo-b": "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6",
  "demo-buyer": "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a",
} as const;

export type WalletMode = keyof typeof DEMO_KEYS | "browser";
export const DEMO_LABELS: Record<WalletMode, string> = {
  "demo-a": "Demo developer A", "demo-b": "Demo developer B", "demo-buyer": "Demo buyer", browser: "Browser wallet",
};

declare global { interface Window { ethereum?: { request: (a: { method: string; params?: unknown[] }) => Promise<unknown> } } }

export const demoAvailable = (cfg: Config) => cfg.chainId === 31337;

export async function getSigner(mode: WalletMode, cfg: Config): Promise<Signer> {
  if (mode !== "browser") {
    if (!demoAvailable(cfg)) throw new Error("Demo wallets only exist on the local chain. Connect a browser wallet.");
    return new Wallet(DEMO_KEYS[mode], new JsonRpcProvider(cfg.rpcUrl));
  }
  if (!window.ethereum) throw new Error("No browser wallet found. Install MetaMask or use a demo wallet on the local chain.");
  const hexId = `0x${cfg.chainId.toString(16)}`;
  try {
    await window.ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId: hexId }] });
  } catch (e) {
    throw new Error(`Switch your wallet to chain ${cfg.chainId} (${cfg.network}) and try again.`, { cause: e });
  }
  const provider = new BrowserProvider(window.ethereum as never);
  await provider.send("eth_requestAccounts", []);
  return provider.getSigner();
}

export const registry = (cfg: Config, runner: Signer) => new Contract(cfg.address, abi, runner);

export async function mintFromAttestation(cfg: Config, signer: Signer, att: Attestation) {
  const m = att.message;
  const tuple = [m.to, m.vintage, m.centroidLatE6, m.centroidLonE6, m.cellsHash, BigInt(m.tonnes), m.scoreBps,
    m.evidenceHash, m.metadataHash, BigInt(m.deadline), BigInt(m.nonce)];
  const c = registry(cfg, signer);
  const tx = await c.mintVerified(tuple, att.cells.map(BigInt), att.metadataURI, att.signature);
  const receipt = await tx.wait();
  let projectId: number | null = null;
  for (const log of receipt.logs) {
    const parsed = c.interface.parseLog(log);
    if (parsed?.name === "ProjectMinted") projectId = Number(parsed.args.projectId);
  }
  return { hash: tx.hash as string, projectId };
}

export async function retireCredits(cfg: Config, signer: Signer, id: number, amount: number, beneficiary: string, reason: string) {
  const tx = await registry(cfg, signer).retire(id, amount, beneficiary, reason);
  await tx.wait();
  return tx.hash as string;
}

export async function transferCredits(cfg: Config, signer: Signer, id: number, to: string, amount: number) {
  const from = await signer.getAddress();
  const tx = await registry(cfg, signer).safeTransferFrom(from, to, id, amount, "0x");
  await tx.wait();
  return tx.hash as string;
}

export async function balanceOf(cfg: Config, signer: Signer, id: number): Promise<number> {
  return Number(await registry(cfg, signer).balanceOf(await signer.getAddress(), id));
}

const FRIENDLY: Record<string, (args: readonly unknown[]) => string> = {
  CellAlreadyClaimed: (a) => `Rejected on-chain: this land already backs project #${a[1]} for the same year. The registry will not issue it twice.`,
  AttestationExpired: () => "The verification expired. Run verification again to get a fresh attestation.",
  NonceAlreadyUsed: () => "This attestation was already used. Each verification can mint once.",
  NotRecipient: () => "Use the same wallet address that you verified the project with.",
  InvalidVerifier: () => "The attestation was not signed by an authorised verifier.",
  ScoreTooLow: () => "The score is below the registry minimum.",
  CellsHashMismatch: () => "The land cells do not match the signed attestation.",
  MetadataHashMismatch: () => "The metadata does not match the signed attestation.",
  ProjectIsRevoked: () => "This project was revoked. Its credits are frozen.",
  EnforcedPause: () => "The registry is paused by its operators.",
  ERC1155InsufficientBalance: () => "This wallet does not hold enough credits.",
  InvalidAmount: () => "Enter an amount above zero.",
};

export function explainError(err: unknown, iface?: Interface): string {
  const e = err as { code?: string | number; revert?: { name: string; args: readonly unknown[] } | null; shortMessage?: string; message?: string; data?: string; info?: { error?: { code?: number } } };
  if (e?.code === "ACTION_REJECTED" || e?.code === 4001 || e?.info?.error?.code === 4001) return "You cancelled the request in your wallet.";
  let revert = e?.revert;
  if (!revert && iface && typeof e?.data === "string") {
    const parsed = iface.parseError(e.data);
    if (parsed) revert = { name: parsed.name, args: parsed.args };
  }
  if (revert && FRIENDLY[revert.name]) return FRIENDLY[revert.name](revert.args);
  if (revert) return `The contract rejected the transaction (${revert.name}).`;
  return e?.shortMessage ?? e?.message ?? "Transaction failed.";
}
