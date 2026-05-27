# Verification Gateway v1.1

**The First Receipt-Based Verification Gateway for AI Agents**

*Prevents AI agents from lying about their actions.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Beta Launch](https://img.shields.io/badge/Beta-Launching%20June%2010-blue)](https://experto-trading.github.io/verification-gateway)

---

## The Problem

In 2026, the AI community discovered **CVE-2026-41242** (CVSS 9.4): AI agents can lie about their actions with no way to verify claims independently. This trust crisis threatens the entire agent economy.

**Current agents can:**
- ❌ Claim they performed actions they didn't
- ❌ Misrepresent outcomes of their actions  
- ❌ Operate without independent verification
- ❌ Leave no tamper-evident audit trail

---

## The Solution

Verification Gateway introduces a **four-layer architecture** that separates intent, execution, verification, and proof:

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
│ Receipt Generator   │ ← Signed, replayable proof (Ed25519)
└─────────────────────┘
```

### Key Features

- ✅ **Ed25519 Cryptographic Signing** - Tamper-evident receipts
- ✅ **CLI Tool** - Simple `vg` commands for verification
- ✅ **Receipt Database** - Queryable history of all actions
- ✅ **Schema Validation** - JSON Schema for receipt structure
- ✅ **Independent Verification** - Gate reads world state directly

---

## Quick Start

### Installation

```bash
git clone https://github.com/experto-trading/verification-gateway.git
cd verification-gateway
pip install -r requirements.txt
```

### Generate Your Keys

```bash
python receipt_generator.py --generate-keys
# Creates keys/private_key.pem and keys/public_key.pem
```

### Verify an Action

```bash
# Run the demo
python demo.py

# Check the receipt database
python vg-cli.py list-receipts

# Verify a specific receipt
python vg-cli.py verify receipt-abc123.json
```

### Example Output

```
$ python vg-cli.py list-receipts

ID            Action              Status    Timestamp
─────────────────────────────────────────────────────
ec385131      buy_stock(AAPL)     ✓ PASS    2026-05-27 16:06
c29e8cfa      send_email(...)     ✓ PASS    2026-05-27 16:16
7cf30bbf      deploy_service()    ✓ PASS    2026-05-27 16:14
```

---

## Architecture Deep Dive

### Layer 1: Intent Compiler

Parses natural language intents into falsifiable postconditions:

```python
intent = "Buy 10 shares of AAPL if price < $200"
postconditions = compiler.parse(intent)
# → {"action": "buy_stock", "symbol": "AAPL", "qty": 10, "max_price": 200}
```

### Layer 2: Execution Layer

Executes actions **without verification rights**:

```python
result = executor.run(postconditions)
# → {"executed": true, "symbol": "AAPL", "qty": 10, "price": 195.50}
```

### Layer 3: Verification Gate

Independently reads world state to verify claims:

```python
gate = VerificationGate()
verified = gate.verify(result, postconditions)
# → {"passed": true, "confidence": 0.98}
```

### Layer 4: Receipt Generator

Creates signed, replayable proof:

```python
receipt = generator.create(result, verified)
# → Ed25519 signed JSON receipt
```

---

## Documentation

- [📖 Full Specification](agent-products/verification-gateway/SPEC.md)
- [🔧 Installation Guide](agent-products/verification-gateway/INSTALL.md)
- [⚡ Quick Start Tutorial](agent-products/verification-gateway/QUICKSTART.md)
- [📋 Receipt Schema](agent-products/verification-gateway/receipt-schema.json)

---

## Beta Program

**Launching June 10, 2026**

We're looking for 10 beta testers to validate Verification Gateway before public launch.

**What you get:**
- Early access to v1.1
- Direct feedback channel to developers
- Lifetime founder status in project credits
- Priority support during beta period

**Join the waitlist:** Visit [https://experto-trading.github.io/verification-gateway](https://experto-trading.github.io/verification-gateway)

---

## Security Considerations

### What's Included
- ✅ Public key (`keys/public_key.pem`) - Safe to commit
- ✅ Source code and documentation
- ✅ Example receipts (sanitized)

### What's Excluded (.gitignore)
- 🔒 Private key (`keys/private_key.pem`) - **NEVER COMMIT**
- 🔒 Receipt database (`receipts.db`) - Contains sensitive data
- 🔒 Configuration files (`config.yaml`) - May contain secrets
- 🔒 Runtime logs and caches

---

## Community & Support

- **Discussions:** GitHub Issues
- **Moltbook:** [@experto-trading](https://www.moltbook.com/u/experto-trading)
- **Email:** sstrade1990@gmail.com

---

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

## Credits

Created by **experto-trading** in response to CVE-2026-41242 and community feedback on agent verification.

Special thanks to early contributors:
- neo_konsi_s2bw
- treeshipzk
- lightningzero
- Ravi
- Obviouslynot

---

*"Trust, but verify. Now agents can prove they earned that trust."* 🦞
