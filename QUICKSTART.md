# Verification Gateway - Quick Start Guide

**Version:** 1.0.0  
**Time to Complete:** 10 minutes

---

## 🚀 60-Second Demo

```bash
cd agent-products/verification-gateway
python3 demo.py
```

You'll see 4 demos:
1. ✅ Market status check
2. ✅ Position verification
3. ✅ Order placement proof
4. ❌ Failed verification (shows tampering detection)

---

## Basic Usage

### 1. Compile an Intent

Convert natural language to verifiable postconditions:

```python
from intent_compiler import IntentCompiler

compiler = IntentCompiler()
compiled = compiler.compile("Check if market is open")

print(f"Action: {compiled.action_type}")
print(f"Postconditions: {len(compiled.postconditions)}")
for pc in compiled.postconditions:
    print(f"  - {pc.claim}")
```

### 2. Verify an Action

Independently verify the outcome:

```python
from verification_gate import VerificationGate

gate = VerificationGate()

# Mock state (replace with actual API response)
mock_state = {'market_status': 'OPEN'}

result = gate.verify_with_mock_state(
    postconditions=compiled.postconditions,
    mock_post_state=mock_state
)

print(f"Status: {result.status}")  # PASS, FAIL, or PARTIAL
print(f"Confidence: {result.confidence:.0%}")
```

### 3. Generate a Receipt

Create cryptographically signed proof:

```python
from receipt_generator import ReceiptGenerator

generator = ReceiptGenerator(algorithm="Ed25519")

receipt = generator.generate(
    intent="Check if market is open",
    action_type='api_call',
    target='dhan_market_status',
    parameters={},
    verification_result=result,
    post_state=mock_state
)

print(f"Receipt ID: {receipt.receipt_id}")
print(f"Signature Valid: {generator.verify_signature(receipt)}")
```

### 4. Store in Database

Persist receipts for audit:

```python
from receipt_db import ReceiptDatabase

db = ReceiptDatabase()
receipt_id = db.store_receipt(receipt)
print(f"Stored: {receipt_id}")
```

---

## CLI Usage

The `vg-cli.py` tool provides command-line access:

### Verify a Receipt

```bash
python3 vg-cli.py verify <receipt_id>
```

### List Recent Receipts

```bash
# Last 24 hours
python3 vg-cli.py list

# Last 7 days
python3 vg-cli.py list --hours 168

# Filter by status
python3 vg-cli.py list --status PASS
```

### Show Statistics

```bash
python3 vg-cli.py status
```

Output:
```
📊 Verification Gateway Statistics
==================================================
Total Receipts: 150
Last 24 Hours: 23

By Status:
   ✅ PASS: 142
   ⚠️  PARTIAL: 5
   ❌ FAIL: 3
```

### Generate Ed25519 Keys

```bash
python3 vg-cli.py generate-key
```

### Search Receipts

```bash
python3 vg-cli.py search "RELIANCE"
python3 vg-cli.py search "order" --limit 10
```

### Export All Receipts

```bash
python3 vg-cli.py export --output backup.json
```

---

## Real-World Examples

### Example 1: Trading Bot Integration

```python
from intent_compiler import IntentCompiler
from verification_gate import VerificationGate, StateReader
from receipt_generator import ReceiptGenerator
from receipt_db import ReceiptDatabase

# Initialize
compiler = IntentCompiler()
gate = VerificationGate()
generator = ReceiptGenerator(algorithm="Ed25519")
db = ReceiptDatabase()

# Your trading bot code
intent = "Buy 50 shares of RELIANCE at 2450"
compiled = compiler.compile(intent)

# Execute trade (your existing code)
order_response = dhan_client.place_order(
    symbol='RELIANCE',
    side='BUY',
    quantity=50,
    price=2450
)

# Verify the trade
verification = gate.verify(
    action_type='transaction',
    target='dhan_orders',
    postconditions=compiled.postconditions,
    post_state=order_response
)

# Generate receipt
receipt = generator.generate(
    intent=intent,
    action_type='transaction',
    target='dhan_orders',
    parameters=compiled.parameters,
    verification_result=verification,
    post_state=order_response,
    session_id="trading-bot-session-001",
    metadata={'executor_id': 'experto-trading'}
)

# Store receipt
db.store_receipt(receipt)

# Report result
if verification.status == 'PASS':
    print(f"✅ Trade verified: {receipt.receipt_id[:8]}...")
else:
    print(f"❌ Verification failed: {verification.failed_invariants}")
```

### Example 2: Multi-Agent Coordination

Agent B depends on Agent A's action:

```python
# Agent A completes action and generates receipt
receipt_a = generate_receipt_for_action_a()
db.store_receipt(receipt_a)

# Agent B includes receipt A in its context
receipt_b = generator.generate(
    intent="Continue after action A",
    action_type='follow_up',
    target='system',
    parameters={},
    verification_result=verification_b,
    post_state=state_b,
    metadata={
        'related_receipts': [receipt_a.receipt_id],
        'dependency_chain': ['action_a', 'action_b']
    }
)
```

### Example 3: Audit Trail Export

```python
db = ReceiptDatabase()

# Export all receipts for compliance audit
all_receipts = db.export_all()

# Filter for specific date range
from datetime import datetime, timedelta
cutoff = datetime.now() - timedelta(days=30)

recent_receipts = [
    r for r in all_receipts 
    if datetime.fromisoformat(r['timestamp']) > cutoff
]

# Save for auditor
import json
with open('audit-trail-q2-2026.json', 'w') as f:
    json.dump(recent_receipts, f, indent=2)

print(f"Exported {len(recent_receipts)} receipts for audit")
```

---

## Custom Invariant Checks

Define your own postconditions:

```python
from intent_compiler import Postcondition

custom_postconditions = [
    Postcondition(
        invariant_id='CUSTOM-001',
        claim="Account balance must be positive",
        expected="balance > 0",
        evidence_path='$.account.balance',
        critical=True
    ),
    Postcondition(
        invariant_id='CUSTOM-002',
        claim="Order quantity must not exceed limit",
        expected="quantity <= 1000",
        evidence_path='$.order.quantity',
        critical=True
    )
]

gate = VerificationGate()
result = gate.verify_with_mock_state(
    postconditions=custom_postconditions,
    mock_post_state={
        'account': {'balance': 50000},
        'order': {'quantity': 50}
    }
)
```

---

## Receipt Schema

Every receipt contains:

```json
{
  "receipt_id": "uuid-v4",
  "version": "1.0.0",
  "timestamp": "ISO-8601",
  "intent_hash": "sha256-of-original-intent",
  "action_taken": {
    "action_type": "transaction",
    "target": "dhan_orders",
    "parameters": {...},
    "executor_id": "agent-name"
  },
  "post_state": {...},
  "invariants_checked": [...],
  "verification_result": {
    "status": "PASS",
    "confidence": 1.0,
    "failed_invariants": []
  },
  "signature": {
    "algorithm": "Ed25519",
    "value": "base64-signature",
    "public_key_id": "key-identifier"
  }
}
```

---

## Common Patterns

### Pattern 1: Wrap Existing Code

```python
# Before
result = my_action(params)

# After
compiled = compiler.compile("Do my action")
result = my_action(params)
verification = gate.verify(..., post_state=result)
receipt = generator.generate(...)
db.store_receipt(receipt)
```

### Pattern 2: Batch Verification

```python
receipts = []
for action in action_list:
    compiled = compiler.compile(action.intent)
    result = execute(action)
    verification = gate.verify(..., post_state=result)
    receipt = generator.generate(...)
    receipts.append(receipt)

# Store all at once
for r in receipts:
    db.store_receipt(r)
```

### Pattern 3: Fail-Fast on Verification

```python
verification = gate.verify(...)
if verification.status != 'PASS':
    raise ValueError(f"Verification failed: {verification.failed_invariants}")
# Continue only if verified
```

---

## Next Steps

- Read [SPEC.md](SPEC.md) for full technical details
- Customize invariants for your domain
- Set up monitoring for failed verifications
- Integrate with your CI/CD pipeline

---

**Built with 🦞 by Experto**  
Questions? Run `python3 demo.py` to see it in action!
