import { describe, expect, it } from "vitest";
import { ndviColor, shortAddr, tonnes } from "./format";
import { explainError } from "./chain";

describe("format", () => {
  it("shortens addresses", () => {
    expect(shortAddr("0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC")).toBe("0x3C44…93BC");
  });
  it("formats tonnes with separators", () => expect(tonnes(12345)).toBe("12,345 t"));
  it("maps NDVI to darker green as vegetation increases", () => {
    const g = (c: string) => Number(c.match(/\d+/g)![0]);
    expect(g(ndviColor(0.85))).toBeLessThan(g(ndviColor(0.1)));
  });
});

describe("explainError", () => {
  it("explains a double-count revert in plain language", () => {
    const msg = explainError({ revert: { name: "CellAlreadyClaimed", args: [5n, 1n] } });
    expect(msg).toContain("project #1");
  });
  it("recognises a cancelled wallet prompt", () => {
    expect(explainError({ code: "ACTION_REJECTED" })).toMatch(/cancelled/i);
  });
  it("falls back to the contract error name", () => {
    expect(explainError({ revert: { name: "SomethingNew", args: [] } })).toContain("SomethingNew");
  });
});
