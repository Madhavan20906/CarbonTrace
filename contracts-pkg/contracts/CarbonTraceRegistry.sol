// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC1155} from "@openzeppelin/contracts/token/ERC1155/ERC1155.sol";
import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {EIP712} from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title CarbonTraceRegistry
 * @notice Carbon-credit registry where a credit can only exist if
 *         (1) an authorised AI verifier signed an attestation for the physical claim, and
 *         (2) the land cells it covers are not already claimed for the same vintage year.
 *
 *  - 1 token unit of ERC-1155 id `projectId` == 1 tCO2e (decimals = 0).
 *  - Land is represented as a set of grid cells (see CELL_SIZE_MICRODEG). The off-chain verifier
 *    rasterises the polygon into cells and commits to them with `cellsHash`.
 *  - Double counting is prevented by `cellClaim[vintage][cell]`: a cell can back at most one
 *    non-revoked project per vintage.
 *  - Retiring burns the credit permanently and records who retired it, for whom and why.
 *  - Revoked projects freeze (no transfer, no retirement) and release their cells.
 */
contract CarbonTraceRegistry is ERC1155, AccessControl, EIP712, Pausable {
    // ───────────── Roles ─────────────
    bytes32 public constant VERIFIER_ROLE = keccak256("VERIFIER_ROLE");
    bytes32 public constant REVOKER_ROLE = keccak256("REVOKER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    // ───────────── Constants ─────────────
    /// Grid resolution in micro-degrees (0.002 deg, roughly 220 m at the equator). Informational:
    /// the verifier computes cell ids as (latIdx << 32 | lonIdx) using this size.
    uint32 public constant CELL_SIZE_MICRODEG = 2000;
    uint256 public constant MAX_CELLS = 256;
    /// Minimum AI plausibility score (basis points) that the contract itself will accept,
    /// independent of what the verifier chooses to sign.
    uint16 public constant MIN_SCORE_BPS = 7000;

    bytes32 private constant ATTESTATION_TYPEHASH = keccak256(
        "Attestation(address to,uint16 vintage,int32 centroidLatE6,int32 centroidLonE6,bytes32 cellsHash,uint256 tonnes,uint16 scoreBps,bytes32 evidenceHash,bytes32 metadataHash,uint256 deadline,uint256 nonce)"
    );

    // ───────────── Types ─────────────
    struct Attestation {
        address to;
        uint16 vintage;
        int32 centroidLatE6;
        int32 centroidLonE6;
        bytes32 cellsHash;
        uint256 tonnes;
        uint16 scoreBps;
        bytes32 evidenceHash;
        bytes32 metadataHash;
        uint256 deadline;
        uint256 nonce;
    }

    struct Project {
        address developer;
        uint16 vintage;
        uint16 scoreBps;
        bool revoked;
        int32 centroidLatE6;
        int32 centroidLonE6;
        uint32 cellCount;
        uint64 mintedAt;
        uint256 tonnes;
        uint256 retired;
        bytes32 evidenceHash;
        bytes32 cellsHash;
        string metadataURI;
    }

    // ───────────── Storage ─────────────
    uint256 public projectCount;
    uint256 public totalMinted;
    uint256 public totalRetired;
    uint256 public totalRevoked;

    mapping(uint256 => Project) public projects;
    /// vintage => cell id => project id (0 = unclaimed)
    mapping(uint16 => mapping(uint64 => uint256)) public cellClaim;
    mapping(uint256 => bool) public nonceUsed;
    /// project id => account => amount that account retired
    mapping(uint256 => mapping(address => uint256)) public retiredBy;

    // ───────────── Events ─────────────
    event ProjectMinted(
        uint256 indexed projectId,
        address indexed developer,
        uint16 vintage,
        uint256 tonnes,
        uint16 scoreBps,
        bytes32 evidenceHash,
        bytes32 cellsHash,
        uint32 cellCount,
        int32 centroidLatE6,
        int32 centroidLonE6,
        string metadataURI
    );
    event Retired(
        uint256 indexed projectId,
        address indexed account,
        uint256 amount,
        string beneficiary,
        string reason
    );
    event ProjectRevoked(uint256 indexed projectId, string reason);

    // ───────────── Errors ─────────────
    error NotRecipient();
    error AttestationExpired();
    error NonceAlreadyUsed();
    error InvalidTonnes();
    error ScoreTooLow(uint16 scoreBps);
    error BadCells();
    error CellsNotSorted();
    error CellsHashMismatch();
    error MetadataHashMismatch();
    error InvalidVerifier(address signer);
    error CellAlreadyClaimed(uint64 cell, uint256 projectId);
    error UnknownProject();
    error ProjectIsRevoked();
    error AlreadyRevoked();
    error InvalidAmount();

    constructor(address admin, address verifier) ERC1155("") EIP712("CarbonTraceRegistry", "1") {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(REVOKER_ROLE, admin);
        _grantRole(PAUSER_ROLE, admin);
        _grantRole(VERIFIER_ROLE, verifier);
    }

    // ───────────── Minting ─────────────

    /**
     * @notice Mint carbon credits for a verified project.
     * @param a            Attestation signed by a VERIFIER_ROLE holder (EIP-712).
     * @param cells        Sorted (strictly ascending) grid cell ids covered by the project.
     * @param metadataURI  URI of the project metadata / evidence bundle.
     * @param signature    Verifier signature over `a`.
     */
    function mintVerified(
        Attestation calldata a,
        uint64[] calldata cells,
        string calldata metadataURI,
        bytes calldata signature
    ) external whenNotPaused returns (uint256 projectId) {
        if (msg.sender != a.to) revert NotRecipient();
        if (block.timestamp > a.deadline) revert AttestationExpired();
        if (nonceUsed[a.nonce]) revert NonceAlreadyUsed();
        if (a.tonnes == 0) revert InvalidTonnes();
        if (a.scoreBps < MIN_SCORE_BPS) revert ScoreTooLow(a.scoreBps);
        if (cells.length == 0 || cells.length > MAX_CELLS) revert BadCells();
        if (keccak256(abi.encodePacked(cells)) != a.cellsHash) revert CellsHashMismatch();
        if (keccak256(bytes(metadataURI)) != a.metadataHash) revert MetadataHashMismatch();

        address signer = ECDSA.recover(_hashTypedDataV4(_structHash(a)), signature);
        if (!hasRole(VERIFIER_ROLE, signer)) revert InvalidVerifier(signer);

        nonceUsed[a.nonce] = true;
        projectId = ++projectCount;

        // Double-count guard: every cell must be free (or held by a revoked project) for this vintage.
        uint64 prev;
        for (uint256 i = 0; i < cells.length; i++) {
            uint64 cell = cells[i];
            if (i > 0 && cell <= prev) revert CellsNotSorted();
            prev = cell;
            uint256 existing = cellClaim[a.vintage][cell];
            if (existing != 0 && !projects[existing].revoked) revert CellAlreadyClaimed(cell, existing);
            cellClaim[a.vintage][cell] = projectId;
        }

        projects[projectId] = Project({
            developer: a.to,
            vintage: a.vintage,
            scoreBps: a.scoreBps,
            revoked: false,
            centroidLatE6: a.centroidLatE6,
            centroidLonE6: a.centroidLonE6,
            cellCount: uint32(cells.length),
            mintedAt: uint64(block.timestamp),
            tonnes: a.tonnes,
            retired: 0,
            evidenceHash: a.evidenceHash,
            cellsHash: a.cellsHash,
            metadataURI: metadataURI
        });
        totalMinted += a.tonnes;

        _mint(a.to, projectId, a.tonnes, "");

        emit ProjectMinted(
            projectId, a.to, a.vintage, a.tonnes, a.scoreBps, a.evidenceHash, a.cellsHash,
            uint32(cells.length), a.centroidLatE6, a.centroidLonE6, metadataURI
        );
    }

    // ───────────── Retirement ─────────────

    /// @notice Permanently burn credits and publish who retired them and why.
    function retire(uint256 projectId, uint256 amount, string calldata beneficiary, string calldata reason)
        external
        whenNotPaused
    {
        Project storage p = projects[projectId];
        if (p.developer == address(0)) revert UnknownProject();
        if (p.revoked) revert ProjectIsRevoked();
        if (amount == 0) revert InvalidAmount();

        _burn(msg.sender, projectId, amount); // reverts on insufficient balance
        p.retired += amount;
        totalRetired += amount;
        retiredBy[projectId][msg.sender] += amount;

        emit Retired(projectId, msg.sender, amount, beneficiary, reason);
    }

    // ───────────── Governance ─────────────

    /// @notice Revoke a project (e.g. fraud found later). Freezes its tokens and releases its cells.
    function revokeProject(uint256 projectId, string calldata reason) external onlyRole(REVOKER_ROLE) {
        Project storage p = projects[projectId];
        if (p.developer == address(0)) revert UnknownProject();
        if (p.revoked) revert AlreadyRevoked();
        p.revoked = true;
        totalRevoked += p.tonnes - p.retired;
        emit ProjectRevoked(projectId, reason);
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    // ───────────── Views ─────────────

    /// @notice Is any cell of `cells` already backing an active project for `vintage`?
    function findConflict(uint16 vintage, uint64[] calldata cells)
        external
        view
        returns (bool conflict, uint64 cell, uint256 projectId)
    {
        for (uint256 i = 0; i < cells.length; i++) {
            uint256 existing = cellClaim[vintage][cells[i]];
            if (existing != 0 && !projects[existing].revoked) return (true, cells[i], existing);
        }
        return (false, 0, 0);
    }

    function domainSeparator() external view returns (bytes32) {
        return _domainSeparatorV4();
    }

    function uri(uint256 id) public view override returns (string memory) {
        return projects[id].metadataURI;
    }

    function supportsInterface(bytes4 interfaceId) public view override(ERC1155, AccessControl) returns (bool) {
        return super.supportsInterface(interfaceId);
    }

    // ───────────── Internals ─────────────

    function _structHash(Attestation calldata a) private pure returns (bytes32) {
        return keccak256(
            abi.encode(
                ATTESTATION_TYPEHASH,
                a.to,
                a.vintage,
                a.centroidLatE6,
                a.centroidLonE6,
                a.cellsHash,
                a.tonnes,
                a.scoreBps,
                a.evidenceHash,
                a.metadataHash,
                a.deadline,
                a.nonce
            )
        );
    }

    /// Revoked credits are frozen; everything is frozen while paused.
    function _update(address from, address to, uint256[] memory ids, uint256[] memory values)
        internal
        override
    {
        _requireNotPaused();
        if (from != address(0)) {
            for (uint256 i = 0; i < ids.length; i++) {
                if (projects[ids[i]].revoked) revert ProjectIsRevoked();
            }
        }
        super._update(from, to, ids, values);
    }
}
