# Deploying to a public testnet (Polygon Amoy or Sepolia)

1. **Create keys.** Deployer: any funded testnet wallet. Verifier: `cd backend && python scripts/gen_verifier_key.py`.
2. **Contracts.** Copy `contracts-pkg/.env.example` to `.env` and fill `DEPLOYER_PRIVATE_KEY`, `AMOY_RPC_URL`, and `VERIFIER_ADDRESS` (from step 1).
   Optionally set `ADMIN_ADDRESS` to a multisig.
   ```bash
   cd contracts-pkg && npm run deploy:amoy
   ```
   This writes `deployments/amoy.json` with the address and ABI. A full 256-cell mint costs several million gas, which is cheap on L2 testnets.
3. **Verifier.** Copy `backend/.env.example` to `backend/.env` and set:
   `RPC_URL`, `DEPLOYMENT_FILE=../deployments/amoy.json`, `VERIFIER_PRIVATE_KEY`, `SATELLITE_PROVIDER=sentinel2`,
   `REFUSE_ON_CONFLICT=true`, `PUBLIC_BASE_URL` (your public API URL), `CORS_ORIGINS` (your site).
   Optional: `PINATA_JWT` for IPFS, `ANTHROPIC_API_KEY` for written explanations.
   Install live mode with `pip install -r requirements-live.txt` (needs GDAL wheels, so use Python 3.11 or 3.12).
4. **Frontend.** `cd frontend && VITE_API_URL=https://your-api npm run build`, then host `dist/` anywhere static.
   Update `src/abi.json` if you changed the contract: copy the `abi` array from `deployments/<network>.json`.
5. **Verify the contract** on the block explorer (Hardhat verify with the same compiler settings: 0.8.24, viaIR, optimizer 200 runs).
6. **Rehearse** one legit mint and one duplicate attempt with your own wallet before recording the demo.

Demo wallets are hidden automatically on any chain other than 31337. On a public network use a browser wallet.
