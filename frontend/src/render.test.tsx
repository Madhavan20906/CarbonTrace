import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Observation } from "./api";
import Report from "./components/Report";

const obs: Observation[] = Array.from({ length: 12 }, (_, i) => ({
  month: i + 1, mean_ndvi: 0.78 - (i === 6 ? 0.4 : 0), p10: 0.7, p90: 0.85, canopy_fraction: 0.9, valid_fraction: i === 6 ? 0.2 : 0.9, scene_id: null,
}));
const checks = [
  { id: "canopy", label: "Forest canopy cover", status: "pass" as const, value: "90% of the site", detail: "d" },
  { id: "clearing", label: "No clearing detected during the year", status: "fail" as const, value: "drop of 0.40 in month 7", detail: "d" },
];

describe("Report", () => {
  it("renders an approved report with trimmed credits and the demo-data banner", () => {
    const html = renderToString(
      <Report approved score={90} claimed={1500} verified={802} capacity={802} areaHa={81} cells={16}
        explanation="Approved." explanationBy="rules" checks={checks} observations={obs} simulated biome="Tropical moist forest" />,
    );
    expect(html).toContain("Verified");
    expect(html).toContain("trimmed to capacity");
    expect(html).toContain("Demo data");
    expect(html).toContain("Forest canopy cover");
  });
  it("renders a rejected report without crashing on missing months", () => {
    const html = renderToString(
      <Report approved={false} score={21} claimed={9000} verified={0} capacity={753} areaHa={169} cells={36}
        explanation="Rejected." explanationBy="claude-sonnet-4-6" checks={checks} observations={obs.slice(0, 5)} simulated={false} biome="x" />,
    );
    expect(html).toContain("Rejected");
    expect(html).not.toContain("Demo data");
    expect(html).toContain("cannot change the decision");
  });
});
