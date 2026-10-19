const { ethers } = require("hardhat");

const TYPES = {
  Attestation: [
    { name: "to", type: "address" },
    { name: "vintage", type: "uint16" },
    { name: "centroidLatE6", type: "int32" },
    { name: "centroidLonE6", type: "int32" },
    { name: "cellsHash", type: "bytes32" },
    { name: "tonnes", type: "uint256" },
    { name: "scoreBps", type: "uint16" },
    { name: "evidenceHash", type: "bytes32" },
    { name: "metadataHash", type: "bytes32" },
    { name: "deadline", type: "uint256" },
    { name: "nonce", type: "uint256" },
  ],
};

function cellsHash(cells) {
  return ethers.keccak256(ethers.solidityPacked(["uint64[]"], [cells]));
}

let nonceCounter = 1n;

async function makeAttestation(registry, verifier, overrides = {}, metadataURI = "ipfs://evidence/1") {
  const cells = overrides.cells ?? [1n, 2n, 3n, 4n];
  const latest = (await ethers.provider.getBlock("latest")).timestamp;
  const att = {
    to: overrides.to,
    vintage: overrides.vintage ?? 2025,
    centroidLatE6: overrides.centroidLatE6 ?? 12_000_000,
    centroidLonE6: overrides.centroidLonE6 ?? 80_000_000,
    cellsHash: overrides.cellsHash ?? cellsHash(cells),
    tonnes: overrides.tonnes ?? 100n,
    scoreBps: overrides.scoreBps ?? 8800,
    evidenceHash: overrides.evidenceHash ?? ethers.id("evidence"),
    metadataHash: overrides.metadataHash ?? ethers.keccak256(ethers.toUtf8Bytes(metadataURI)),
    deadline: overrides.deadline ?? BigInt(latest + 3600),
    nonce: overrides.nonce ?? nonceCounter++,
  };
  const net = await ethers.provider.getNetwork();
  const domain = {
    name: "CarbonTraceRegistry",
    version: "1",
    chainId: net.chainId,
    verifyingContract: await registry.getAddress(),
  };
  const signature = await verifier.signTypedData(domain, TYPES, att);
  return { att, cells, metadataURI, signature };
}

module.exports = { makeAttestation, cellsHash, TYPES };
