require("dotenv").config();
require("@nomicfoundation/hardhat-ethers");
require("@nomicfoundation/hardhat-chai-matchers");
const path = require("path");
const { subtask } = require("hardhat/config");
const { TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD } = require("hardhat/builtin-tasks/task-names");

// Use the pinned `solc` npm package (solc-js) instead of downloading a native compiler.
// This makes builds reproducible and works in offline / locked-down CI environments.
subtask(TASK_COMPILE_SOLIDITY_GET_SOLC_BUILD, async (args, hre, runSuper) => {
  if (args.solcVersion === require("solc/package.json").version) {
    const compilerPath = require.resolve("solc/soljson.js");
    return { compilerPath, isSolcJs: true, version: args.solcVersion, longVersion: args.solcVersion };
  }
  return runSuper();
});

const { DEPLOYER_PRIVATE_KEY, AMOY_RPC_URL, SEPOLIA_RPC_URL } = process.env;
const accounts = DEPLOYER_PRIVATE_KEY ? [DEPLOYER_PRIVATE_KEY] : [];

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.24",
    settings: { viaIR: true, optimizer: { enabled: true, runs: 200 }, evmVersion: "cancun" },
  },
  networks: {
    hardhat: { chainId: 31337 },
    localhost: { url: process.env.LOCAL_RPC_URL || "http://127.0.0.1:8545", chainId: 31337 },
    ...(AMOY_RPC_URL ? { amoy: { url: AMOY_RPC_URL, chainId: 80002, accounts } } : {}),
    ...(SEPOLIA_RPC_URL ? { sepolia: { url: SEPOLIA_RPC_URL, chainId: 11155111, accounts } } : {}),
  },
  paths: { sources: "./contracts", tests: "./test", cache: "./cache", artifacts: "./artifacts" },
};
