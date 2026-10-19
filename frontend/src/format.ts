export const shortAddr = (a: string) => `${a.slice(0, 6)}…${a.slice(-4)}`;
export const shortHash = (h: string) => `${h.slice(0, 10)}…${h.slice(-6)}`;
export const tonnes = (n: number) => `${n.toLocaleString("en-US")} t`;
export const date = (unix: number) =>
  new Date(unix * 1000).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** NDVI to colour: bare soil brown, through khaki and lime, to deep forest green. */
const STOPS: [number, [number, number, number]][] = [
  [0.0, [150, 118, 74]], [0.2, [196, 170, 92]], [0.4, [168, 186, 76]], [0.6, [88, 160, 72]], [0.8, [24, 110, 62]],
];
export function ndviColor(v: number): string {
  if (v <= STOPS[0][0]) return `rgb(${STOPS[0][1].join(",")})`;
  for (let i = 1; i < STOPS.length; i++) {
    const [x1, c1] = STOPS[i];
    const [x0, c0] = STOPS[i - 1];
    if (v <= x1) {
      const t = (v - x0) / (x1 - x0);
      return `rgb(${c0.map((c, k) => Math.round(c + (c1[k] - c) * t)).join(",")})`;
    }
  }
  return `rgb(${STOPS[STOPS.length - 1][1].join(",")})`;
}
