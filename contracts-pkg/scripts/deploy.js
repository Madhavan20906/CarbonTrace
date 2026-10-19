// Deploys CarbonTraceRegistry and writes deployments/<network>.json (address, ABI, chainId).
// The verifier address is the public address of the AI verification service's signing key.
require("dotenv").config();
const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

async function main() {
  const { ethers, network } = hre;
  const [deployer] = await ethers.getSigners();

  // Local dev default: well-known Hardhat account #1 acts as the verifier (see backend/.env.example).
  const verifier = process.env.VERIFIER_ADDRESS || (await ethers.getSigners())[1].address;
  const admin = process.env.ADMIN_ADDRESS || deployer.address;

  console.log(`Network:   ${network.name}`);
  console.log(`Deployer:  ${deployer.address}`);
  console.log(`Admin:     ${admin}`);
  console.log(`Verifier:  ${verifier}`);

  const Registry = await ethers.getContractFactory("CarbonTraceRegistry");
  const registry = await Registry.deploy(admin, verifier);
  await registry.waitForDeployment();
  const address = await registry.getAddress();
  const chainId = Number((await ethers.provider.getNetwork()).chainId);
  const deployBlock = (await registry.deploymentTransaction().wait()).blockNumber;
  console.log(`CarbonTraceRegistry deployed to ${address} (block ${deployBlock})`);

  const artifact = await hre.artifacts.readArtifact("CarbonTraceRegistry");
  const out = { network: network.name, chainId, address, deployBlock, admin, verifier, abi: artifact.abi };
  const dir = path.join(__dirname, "..", "..", "deployments");
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, `${network.name}.json`), JSON.stringify(out, null, 2));
  console.log(`Wrote deployments/${network.name}.json`);
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
