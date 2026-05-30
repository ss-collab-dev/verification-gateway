# Verification Gateway - Technical Specification

**Version:** 1.1.0 (Production Beta)  
**Date:** May 27, 2026  
**Status:** Production Ready Beta  

---

## Executive Summary

The Verification Gateway is a receipt-based verification system that prevents AI agents from lying about their actions. It was designed in response to community panic around CVE-2026-41242 (CVSS 9.4) and market signals showing agents specifying architectural requirements as procurement language.

### The Problem

AI agents can currently:
- Claim they performed actions they didn't
- Misrepresent outcomes of their actions
- Operate without independent verification
- Leave no tamper-evident audit trail

### The Solution

A four-layer architecture that separates **intent**, **execution**, **verification**, and **proof**:

```
┌─────────────────────┐
│ Intent Compiler     │ ← Emits falsifiable postconditions
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Execution Layer     │ ← Runs actions, NO verification rights
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Verification Gate   │ ← Independent readback of world state
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Receipt Generator   │ ← Signed, replayable proof
└─────────────────────┘
```

---

## Architecture Overview

### Layer 1: Intent Compiler

**Purpose:** Convert natural language agent intents into structured, falsifiable postconditions.

**Input:** Natural language intent (e.g., "Check if market is open")

**Output:** `CompiledIntent` with:
- `intent_hash`: SHA-256 hash of original intent
- `action_type`: Classified action (api_call, transaction, etc.)
- `target`: Target system/resource
- `postconditions`: List of falsifiable claims
- `invariants`: Human-readable invariant descriptions

**Key Principle:** Postconditions must be falsifiable—each claim can be definitively proven true or false.

**Example:**
```python
intent = "Check if market is open"
compiled = compiler.compile(intent)

# Output:
{
  "intent_hash": "b3393146326b7055...",
  "action_type": "api_call",
  "target": "https://api.dhan.co/market-status",
  "postconditions": [
    {
      "invariant_id": "INV-001",
      "claim": "Market status must be a valid state",
      "expected": "market_status in ['OPEN', 'CLOSED', 'PRE_OPEN', 'POST_CLOSE']",
      "evidence_path": "$.market_status",
      "critical": true
    }
  ]
}
```

### Layer 2: Execution Layer

**Purpose:** Perform the actual action (API call, file operation, transaction).

**Critical Constraint:** The Execution Layer has **NO verification rights**. It cannot:
- Verify its own outcomes
- Generate receipts
- Modify verification logic

This separation prevents agents from self-certifying their actions.

**Implementation:** Application-specific. For trading bots, this is the Dhan API client. For file operations, this is the filesystem handler.

### Layer 3: Verification Gate

**Purpose:** Independently read world state and verify claimed postconditions.

**Key Principles:**
- **Zero shared state** with Execution Layer
- All reads happen **after** action completion
- Evidence is captured and included in results
- Every check is falsifiable (PASS/FAIL)

**Components:**

#### StateReader
Independent state reader with no shared connections:
```python
reader = StateReader()
reader.register_source('dhan_positions', lambda p: dhan_api.get_positions())
snapshot = reader.read('dhan_positions', 'api_get')
```

#### InvariantChecker
Evaluates postconditions against actual state:
- Supports JSON path extraction (`$.market_status`)
- Safe expression evaluation (restricted namespace)
- Detailed evidence capture

**Output:** `VerificationResult` with:
- `status`: PASS, FAIL, PARTIAL, or UNVERIFIED
- `confidence`: 0.0 to 1.0 score
- `invariant_results`: Detailed check results
- `failed_invariants`: List of failed check IDs

### Layer 4: Receipt Generator

**Purpose:** Create cryptographically signed, replayable proof of verification.

**Receipt Schema Fields:**
| Field | Description |
|-------|-------------|
| `receipt_id` | UUID v4 identifier |
| `version` | Schema version (1.0.0) |
| `timestamp` | ISO 8601 timestamp |
| `intent_hash` | SHA-256 of original intent |
| `action_taken` | What action was performed |
| `pre_state` | State before action (optional) |
| `post_state` | State after action |
| `invariants_checked` | Results of each invariant check |
| `verification_result` | Overall PASS/FAIL status |
| `context_bundle` | Session, environment, metadata |
| `signature` | Cryptographic signature |

**Signing Algorithms:**
- **HMAC-SHA256** (default): Symmetric, fast, requires shared secret
- **Ed25519** (optional): Asymmetric, public-key verification

**Security Properties:**
- Receipts are immutable once signed
- Signature covers all critical fields
- Anyone with the public key can verify
- Receipts are replayable (can re-verify independently)

---

## API Documentation

### IntentCompiler

```python
from intent_compiler import IntentCompiler

compiler = IntentCompiler()

# Compile single intent
compiled = compiler.compile("Check if market is open")

# Compile batch
compiled_list = compiler.compile_batch([intent1, intent2])

# Serialize
json_str = compiler.to_json(compiled)

# Deserialize
compiled = compiler.from_json(json_str)
```

### VerificationGate

```python
from verification_gate import VerificationGate, StateReader

# Create independent state reader
reader = StateReader()
reader.register_source('my_api', lambda p: fetch_state())

# Create gate
gate = VerificationGate(reader)

# Verify action
result = gate.verify(
    action_type='api_call',
    target='my_api',
    postconditions=compiled.postconditions,
    post_state=actual_state
)

# Check result
if result.status == 'PASS':
    print(f"Verified with {result.confidence:.0%} confidence")
else:
    print(f"Failed invariants: {result.failed_invariants}")
```

### ReceiptGenerator

```python
from receipt_generator import ReceiptGenerator

# Initialize with persistent key (production)
import os
signing_key = os.environ['VERIFICATION_GATEWAY_KEY'].encode()
generator = ReceiptGenerator(signing_key=signing_key)

# Generate receipt
receipt = generator.generate(
    intent="Check if market is open",
    action_type='api_call',
    target='https://api.dhan.co/market-status',
    parameters={},
    verification_result=result,
    post_state=actual_state,
    session_id="agent:main:telegram:direct:1388143890",
    metadata={'executor_id': 'experto-trading'}
)

# Save receipt
generator.save_receipt(receipt, 'receipt.json')

# Verify signature later
is_valid = generator.verify_signature(receipt)
```

---

## Security Model

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Agent lies about action outcome | Independent Verification Gate reads actual state |
| Agent tampers with verification code | Code integrity checks, signed deployments |
| Agent replays old receipts | Timestamps + nonce in context_bundle |
| Attacker forges receipts | Cryptographic signatures (HMAC/Ed25519) |
| Signing key compromised | Key rotation, public key distribution |

### Trust Boundaries

```
┌─────────────────────────────────────────┐
│  Trusted Zone                           │
│  ┌─────────────┐  ┌──────────────────┐  │
│  │ Verification│  │ Receipt          │  │
│  │ Gate        │  │ Generator        │  │
│  └─────────────┘  └──────────────────┘  │
│         ▲               ▲                │
│         │               │                │
│  ───────┼───────────────┼────────        │
│         │               │                │
│  ┌──────┴──────┐        │                │
│  │ Execution   │        │                │
│  │ Layer       │◄───────┘                │
│  └─────────────┘                         │
└─────────────────────────────────────────┘
         ▲
         │ Untrusted (Agent-controlled)
```

**Key Insight:** The Execution Layer is untrusted. All verification happens outside its control.

### Signature Coverage

Signed fields (cannot be tampered with):
- `intent_hash`
- `action_taken`
- `post_state`
- `invariants_checked`
- `timestamp`

Unsigned fields (may change without invalidating signature):
- `receipt_id`
- `version`
- `context_bundle.metadata`

---

## Use Cases

### 1. Trading Bot Verification

**Scenario:** Bot claims it placed a buy order for RELIANCE.

**Flow:**
1. Intent: "Buy 50 shares of RELIANCE at 2450"
2. Execution: POST /orders to Dhan API
3. Verification: GET /orders/{order_id} to confirm
4. Receipt: Signed proof with order details

**Receipt proves:**
- Order was actually placed
- Order ID matches claim
- Status is correct (OPEN/PENDING/REJECTED)
- Price and quantity match intent

### 2. File Operation Audit

**Scenario:** Agent claims it updated configuration file.

**Flow:**
1. Intent: "Update config.json with new API key"
2. Execution: Write to config.json
3. Verification: Read config.json, hash comparison
4. Receipt: Proof of file state change

**Receipt proves:**
- File was modified
- New hash matches expected
- No unauthorized changes

### 3. Multi-Agent Coordination

**Scenario:** Agent A depends on Agent B's action.

**Flow:**
1. Agent B completes action → generates Receipt B
2. Agent A includes Receipt B ID in its context_bundle
3. Auditor can trace dependency chain

**Receipt proves:**
- Causal relationship between actions
- No race conditions or missed dependencies

### 4. Compliance & Audit

**Scenario:** Regulator requests proof of trading activity.

**Flow:**
1. Export all receipts for date range
2. Provide public key for verification
3. Regulator independently verifies each receipt

**Receipt proves:**
- Each trade was verified against actual state
- No post-hoc modifications
- Complete audit trail

---

## Integration Guide

### Quick Start (5 minutes)

```bash
cd agent-products/verification-gateway
python3 demo.py
```

### Adding to Your Agent

**Step 1:** Import modules
```python
from intent_compiler import IntentCompiler
from verification_gate import VerificationGate
from receipt_generator import ReceiptGenerator
```

**Step 2:** Wrap your action
```python
# Before your action
compiled = compiler.compile(your_intent)

# Your existing action
result = your_action(compiled.parameters)

# After your action
gate = VerificationGate()
verification = gate.verify(
    action_type='your_action',
    target='your_target',
    postconditions=compiled.postconditions,
    post_state=result
)

receipt = generator.generate(
    intent=your_intent,
    action_type='your_action',
    target='your_target',
    parameters=compiled.parameters,
    verification_result=verification,
    post_state=result
)
```

**Step 3:** Store receipts
```python
generator.save_receipt(receipt, f"receipts/{receipt.receipt_id}.json")
```

### Production Checklist

- [ ] Generate persistent signing key (don't use random)
- [ ] Store key securely (HSM, secrets manager)
- [ ] Distribute public key to verifiers
- [ ] Set up receipt storage (database, S3)
- [ ] Configure state readers for your systems
- [ ] Add custom postconditions for domain-specific actions
- [ ] Set up monitoring for failed verifications
- [ ] Document receipt retention policy

---

## File Structure

```
agent-products/verification-gateway/
├── SPEC.md                    # This document
├── INSTALL.md                 # Setup instructions [NEW in v1.1]
├── QUICKSTART.md              # Quick start guide [NEW in v1.1]
├── receipt-schema.json        # JSON Schema for receipts
├── intent_compiler.py         # Intent → postconditions
├── verification_gate.py       # Independent verification (fixed in v1.1)
├── receipt_generator.py       # Signed receipt generation (Ed25519 in v1.1)
├── receipt_db.py              # SQLite database [NEW in v1.1]
├── vg-cli.py                  # CLI tool [NEW in v1.1]
├── demo.py                    # Integration examples
├── keys/                      # Ed25519 key storage [NEW in v1.1]
│   ├── private_key.pem
│   └── public_key.pem
└── receipts.db                # SQLite database [generated]
```

---

## Success Criteria (MVP)

- [x] All 6 files created and functional
- [x] Demo runs end-to-end without errors
- [x] Receipt schema is replayable and falsifiable
- [x] Verification gate is truly independent (no shared state)
- [x] Spec document is clear enough for external contributors

## Success Criteria (v1.1 Production Beta)

- [x] All 4 demos pass without errors
- [x] Ed25519 asymmetric signing implemented and working
- [x] SQLite receipt database with indexing
- [x] CLI tool for verification and management
- [x] Complete documentation (INSTALL.md, QUICKSTART.md)
- [x] Array/object invariant checks fixed
- [x] Type coercion for numeric comparisons

---

## Future Enhancements

### Phase 2 (Post-MVP) - ✅ COMPLETE in v1.1
- [x] Ed25519 asymmetric signing
- [x] Receipt database with indexing
- [x] CLI tool for developers
- [x] Complete documentation

### Phase 2 (Future)
- [ ] Real-time verification dashboard
- [ ] Webhook notifications for failed verifications
- [ ] Multi-signature receipts (multi-agent consensus)

### Phase 3 (Advanced)
- [ ] Zero-knowledge proofs for privacy-preserving verification
- [ ] Blockchain anchoring for immutable timestamping
- [ ] Automated invariant discovery from agent behavior
- [ ] Cross-agent receipt validation

---

## References

- Research Report: `/ai-agent-world/research/daily-reports/2026-05-27-research.md`
- CVE-2026-41242: Schema compilation attack vulnerability (CVSS 9.4)
- Moltbook Research: 1,144+ comments, critical WTP signals
- Dhan Trading API: Primary integration target

---

**Built with 🦞 by Experto**  
*"The future of honest agents"*
