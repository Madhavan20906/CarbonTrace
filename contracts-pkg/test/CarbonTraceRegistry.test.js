const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");
const { makeAttestation, cellsHash } = require("./helpers");

describe("CarbonTraceRegistry", () => {
  let registry, admin, verifier, dev, dev2, buyer, rando;

  beforeEach(async () => {
    [admin, verifier, dev, dev2, buyer, rando] = await ethers.getSigners();
    const F = await ethers.getContractFactory("CarbonTraceRegistry");
    registry = await F.deploy(admin.address, verifier.address);
  });

  const mint = async (signer, sa) =>
    registry.connect(signer).mintVerified(sa.att, sa.cells, sa.metadataURI, sa.signature);

  describe("minting", () => {
    it("mints verified credits to the developer and records the project", async () => {
      const sa = await makeAttestation(registry, verifier, { to: dev.address, tonnes: 250n });
      await expect(mint(dev, sa))
        .to.emit(registry, "ProjectMinted")
        .withArgs(1n, dev.address, 2025, 250n, 8800, sa.att.evidenceHash, sa.att.cellsHash, 4, 12_000_000, 80_000_000, sa.metadataURI);
      expect(await registry.balanceOf(dev.address, 1)).to.equal(250n);
      expect(await registry.totalMinted()).to.equal(250n);
      const p = await registry.projects(1);
      expect(p.developer).to.equal(dev.address);
      expect(p.revoked).to.equal(false);
      expect(await registry.uri(1)).to.equal(sa.metadataURI);
    });

    it("rejects the SAME polygon claimed again in the same vintage (double counting)", async () => {
      const a = await makeAttestation(registry, verifier, { to: dev.address });
      await mint(dev, a);
      const b = await makeAttestation(registry, verifier, { to: dev2.address });
      await expect(mint(dev2, b)).to.be.revertedWithCustomError(registry, "CellAlreadyClaimed").withArgs(1n, 1n);
      expect(await registry.projectCount()).to.equal(1n);
      expect(await registry.balanceOf(dev2.address, 2)).to.equal(0n);
    });

    it("rejects a partially overlapping polygon", async () => {
      await mint(dev, await makeAttestation(registry, verifier, { to: dev.address, cells: [10n, 11n, 12n] }));
      const overlap = await makeAttestation(registry, verifier, { to: dev2.address, cells: [12n, 13n, 14n] });
      await expect(mint(dev2, overlap)).to.be.revertedWithCustomError(registry, "CellAlreadyClaimed").withArgs(12n, 1n);
    });

    it("allows the same land in a different vintage year", async () => {
      await mint(dev, await makeAttestation(registry, verifier, { to: dev.address, vintage: 2024 }));
      await mint(dev, await makeAttestation(registry, verifier, { to: dev.address, vintage: 2025 }));
      expect(await registry.projectCount()).to.equal(2n);
    });

    it("allows adjacent, non-overlapping land", async () => {
      await mint(dev, await makeAttestation(registry, verifier, { to: dev.address, cells: [1n, 2n] }));
      await mint(dev2, await makeAttestation(registry, verifier, { to: dev2.address, cells: [3n, 4n] }));
      expect(await registry.projectCount()).to.equal(2n);
    });

    it("rejects a signature from an account without VERIFIER_ROLE", async () => {
      const sa = await makeAttestation(registry, rando, { to: dev.address });
      await expect(mint(dev, sa)).to.be.revertedWithCustomError(registry, "InvalidVerifier").withArgs(rando.address);
    });

    it("rejects tampered attestation fields (tonnes inflated after signing)", async () => {
      const sa = await makeAttestation(registry, verifier, { to: dev.address, tonnes: 100n });
      const tampered = { ...sa.att, tonnes: 1_000_000n };
      await expect(registry.connect(dev).mintVerified(tampered, sa.cells, sa.metadataURI, sa.signature))
        .to.be.revertedWithCustomError(registry, "InvalidVerifier");
    });

    it("rejects swapped cells (cellsHash mismatch)", async () => {
      const sa = await makeAttestation(registry, verifier, { to: dev.address, cells: [1n, 2n, 3n] });
      await expect(registry.connect(dev).mintVerified(sa.att, [1n, 2n, 99n], sa.metadataURI, sa.signature))
        .to.be.revertedWithCustomError(registry, "CellsHashMismatch");
    });

    it("rejects swapped metadata URI", async () => {
      const sa = await makeAttestation(registry, verifier, { to: dev.address });
      await expect(registry.connect(dev).mintVerified(sa.att, sa.cells, "ipfs://evil", sa.signature))
        .to.be.revertedWithCustomError(registry, "MetadataHashMismatch");
    });

    it("rejects unsorted or duplicate cells", async () => {
      const unsorted = await makeAttestation(registry, verifier, { to: dev.address, cells: [3n, 2n, 1n] });
      await expect(mint(dev, unsorted)).to.be.revertedWithCustomError(registry, "CellsNotSorted");
      const dup = await makeAttestation(registry, verifier, { to: dev.address, cells: [1n, 1n] });
      await expect(mint(dev, dup)).to.be.revertedWithCustomError(registry, "CellsNotSorted");
    });

    it("rejects submission by anyone other than the attested recipient", async () => {
      const sa = await makeAttestation(registry, verifier, { to: dev.address });
      await expect(mint(rando, sa)).to.be.revertedWithCustomError(registry, "NotRecipient");
    });

    it("rejects expired attestations", async () => {
      const sa = await makeAttestation(registry, verifier, { to: dev.address });
      await time.increase(7200);
      await expect(mint(dev, sa)).to.be.revertedWithCustomError(registry, "AttestationExpired");
    });

    it("rejects replay of a used nonce", async () => {
      const sa = await makeAttestation(registry, verifier, { to: dev.address, nonce: 777n });
      await mint(dev, sa);
      const replay = await makeAttestation(registry, verifier, { to: dev.address, nonce: 777n, cells: [50n] });
      await expect(mint(dev, replay)).to.be.revertedWithCustomError(registry, "NonceAlreadyUsed");
    });

    it("enforces the on-chain minimum score even if the verifier signs a low one", async () => {
      const sa = await makeAttestation(registry, verifier, { to: dev.address, scoreBps: 6500 });
      await expect(mint(dev, sa)).to.be.revertedWithCustomError(registry, "ScoreTooLow").withArgs(6500);
    });

    it("rejects zero tonnes and empty / oversized cell sets", async () => {
      const zero = await makeAttestation(registry, verifier, { to: dev.address, tonnes: 0n });
      await expect(mint(dev, zero)).to.be.revertedWithCustomError(registry, "InvalidTonnes");
      const empty = await makeAttestation(registry, verifier, { to: dev.address, cells: [] });
      await expect(mint(dev, empty)).to.be.revertedWithCustomError(registry, "BadCells");
      const big = Array.from({ length: 257 }, (_, i) => BigInt(i + 1));
      const huge = await makeAttestation(registry, verifier, { to: dev.address, cells: big });
      await expect(mint(dev, huge)).to.be.revertedWithCustomError(registry, "BadCells");
    });

    it("accepts the maximum number of cells", async () => {
      const cells = Array.from({ length: 256 }, (_, i) => BigInt(i + 1000));
      const sa = await makeAttestation(registry, verifier, { to: dev.address, cells });
      await mint(dev, sa);
      expect((await registry.projects(1)).cellCount).to.equal(256n);
    });

    it("matches cellsHash computed off-chain with packed 32-byte elements", async () => {
      const sa = await makeAttestation(registry, verifier, { to: dev.address, cells: [5n, 9n] });
      expect(sa.att.cellsHash).to.equal(cellsHash([5n, 9n]));
      await mint(dev, sa);
    });
  });

  describe("findConflict view", () => {
    it("reports overlaps before sending a transaction", async () => {
      await mint(dev, await makeAttestation(registry, verifier, { to: dev.address, cells: [1n, 2n] }));
      const [c, cell, pid] = await registry.findConflict(2025, [2n, 3n]);
      expect(c).to.equal(true);
      expect(cell).to.equal(2n);
      expect(pid).to.equal(1n);
      const [c2] = await registry.findConflict(2024, [2n, 3n]);
      expect(c2).to.equal(false);
    });
  });

  describe("retirement", () => {
    beforeEach(async () => {
      await mint(dev, await makeAttestation(registry, verifier, { to: dev.address, tonnes: 100n }));
      await registry.connect(dev).safeTransferFrom(dev.address, buyer.address, 1, 60n, "0x");
    });

    it("burns credits and publishes beneficiary and reason", async () => {
      await expect(registry.connect(buyer).retire(1, 40n, "Acme Corp", "FY2026 scope 1 offset"))
        .to.emit(registry, "Retired")
        .withArgs(1n, buyer.address, 40n, "Acme Corp", "FY2026 scope 1 offset");
      expect(await registry.balanceOf(buyer.address, 1)).to.equal(20n);
      expect(await registry.totalRetired()).to.equal(40n);
      expect((await registry.projects(1)).retired).to.equal(40n);
      expect(await registry.retiredBy(1, buyer.address)).to.equal(40n);
    });

    it("cannot retire more than the balance or zero, or an unknown project", async () => {
      await expect(registry.connect(buyer).retire(1, 61n, "x", "y")).to.be.reverted;
      await expect(registry.connect(buyer).retire(1, 0n, "x", "y")).to.be.revertedWithCustomError(registry, "InvalidAmount");
      await expect(registry.connect(buyer).retire(99, 1n, "x", "y")).to.be.revertedWithCustomError(registry, "UnknownProject");
    });

    it("retired credits cannot be transferred again (they no longer exist)", async () => {
      await registry.connect(buyer).retire(1, 60n, "Acme", "offset");
      await expect(registry.connect(buyer).safeTransferFrom(buyer.address, rando.address, 1, 1n, "0x")).to.be.reverted;
    });
  });

  describe("revocation", () => {
    beforeEach(async () => {
      await mint(dev, await makeAttestation(registry, verifier, { to: dev.address, tonnes: 100n, cells: [1n, 2n] }));
    });

    it("only REVOKER_ROLE can revoke", async () => {
      await expect(registry.connect(rando).revokeProject(1, "nope")).to.be.reverted;
    });

    it("freezes transfers and retirement of a revoked project", async () => {
      await expect(registry.revokeProject(1, "satellite re-check failed")).to.emit(registry, "ProjectRevoked");
      await expect(registry.connect(dev).safeTransferFrom(dev.address, buyer.address, 1, 1n, "0x"))
        .to.be.revertedWithCustomError(registry, "ProjectIsRevoked");
      await expect(registry.connect(dev).retire(1, 1n, "x", "y")).to.be.revertedWithCustomError(registry, "ProjectIsRevoked");
      expect(await registry.totalRevoked()).to.equal(100n);
      await expect(registry.revokeProject(1, "again")).to.be.revertedWithCustomError(registry, "AlreadyRevoked");
    });

    it("releases the land so a legitimate claimant can re-register it", async () => {
      await registry.revokeProject(1, "fraud");
      await mint(dev2, await makeAttestation(registry, verifier, { to: dev2.address, cells: [1n, 2n] }));
      expect((await registry.projects(2)).developer).to.equal(dev2.address);
    });
  });

  describe("governance and safety", () => {
    it("pause blocks minting, transfers and retirement; unpause restores", async () => {
      await mint(dev, await makeAttestation(registry, verifier, { to: dev.address }));
      await registry.pause();
      const sa = await makeAttestation(registry, verifier, { to: dev.address, cells: [900n] });
      await expect(mint(dev, sa)).to.be.revertedWithCustomError(registry, "EnforcedPause");
      await expect(registry.connect(dev).safeTransferFrom(dev.address, buyer.address, 1, 1n, "0x"))
        .to.be.revertedWithCustomError(registry, "EnforcedPause");
      await registry.unpause();
      await mint(dev, sa);
    });

    it("only PAUSER_ROLE can pause", async () => {
      await expect(registry.connect(rando).pause()).to.be.reverted;
    });

    it("rotating the verifier invalidates old signatures", async () => {
      const role = await registry.VERIFIER_ROLE();
      const old = await makeAttestation(registry, verifier, { to: dev.address });
      await registry.revokeRole(role, verifier.address);
      await expect(mint(dev, old)).to.be.revertedWithCustomError(registry, "InvalidVerifier");
      await registry.grantRole(role, rando.address);
      await mint(dev, await makeAttestation(registry, rando, { to: dev.address }));
    });
  });
});
