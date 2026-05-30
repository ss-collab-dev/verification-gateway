# Verification Gateway - Installation Guide

**Version:** 1.0.0 (Production Beta)  
**Last Updated:** May 27, 2026

---

## Quick Install (5 minutes)

```bash
# Clone or navigate to the verification-gateway directory
cd agent-products/verification-gateway

# Install Python dependencies
pip3 install cryptography --break-system-packages

# Verify installation
python3 demo.py
```

That's it! You're ready to verify agent actions. 🦞

---

## System Requirements

- **Python:** 3.8 or higher
- **OS:** Linux, macOS, or Windows (WSL)
- **Disk Space:** ~10 MB for code + database
- **Memory:** 50 MB minimum

### Optional Dependencies

| Package | Purpose | Required For |
|---------|---------|--------------|
| `cryptography` | Ed25519 signing | Asymmetric signatures |
| `sqlite3` | Receipt storage | Built into Python |

---

## Step-by-Step Installation

### Step 1: Verify Python Version

```bash
python3 --version
# Should show: Python 3.8.x or higher
```

### Step 2: Install Dependencies

```bash
# Core dependency for Ed25519 signing
pip3 install cryptography

# If you get permission errors on Linux/macOS:
pip3 install cryptography --break-system-packages

# Or use a virtual environment (recommended):
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows
pip install cryptography
```

### Step 3: Verify Installation

Run the demo to ensure everything works:

```bash
python3 demo.py
```

Expected output:
```
🦞🦞🦞 VERIFICATION GATEWAY - INTEGRATION DEMO 🦞🦞🦞
...
✅ Generated 4 receipts
DEMO COMPLETE - The future of honest agents is here!
```

### Step 4: Generate Ed25519 Keys (Optional but Recommended)

For production use, generate a persistent keypair:

```bash
python3 vg-cli.py generate-key
```

This creates:
- `keys/private_key.pem` - Keep this secret! 🔒
- `keys/public_key.pem` - Share with verifiers

---

## Directory Structure

After installation, your directory should look like:

```
agent-products/verification-gateway/
├── SPEC.md                    # Technical specification
├── INSTALL.md                 # This file
├── QUICKSTART.md              # Usage examples
├── receipt-schema.json        # Receipt JSON schema
├── intent_compiler.py         # Intent → postconditions
├── verification_gate.py       # Independent verification
├── receipt_generator.py       # Signed receipt generation
├── receipt_db.py              # SQLite database
├── vg-cli.py                  # Command-line interface
├── demo.py                    # Integration demo
├── keys/                      # Ed25519 keys (generated)
│   ├── private_key.pem
│   └── public_key.pem
└── receipts.db                # SQLite database (generated)
```

---

## Configuration

### Environment Variables (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `VG_DATABASE_PATH` | Custom SQLite database location | `receipts.db` |
| `VG_KEYS_DIR` | Custom keys directory | `./keys/` |
| `VG_SIGNING_ALGORITHM` | Default signing algorithm | `Ed25519` |

Example:
```bash
export VG_DATABASE_PATH=/var/lib/vg/receipts.db
export VG_SIGNING_ALGORITHM=Ed25519
```

---

## Integration with Trading Bots

### For Dhan Trading API Users

The Verification Gateway is pre-configured to work with Dhan Trading API. No additional setup required.

To integrate with your trading bot:

```python
from intent_compiler import IntentCompiler
from verification_gate import VerificationGate
from receipt_generator import ReceiptGenerator
from receipt_db import ReceiptDatabase

# Initialize components
compiler = IntentCompiler()
gate = VerificationGate()
generator = ReceiptGenerator(algorithm="Ed25519")
db = ReceiptDatabase()

# Before action
intent = "Buy 50 shares of RELIANCE at 2450"
compiled = compiler.compile(intent)

# Your existing action (Dhan API call)
order_result = dhan_client.place_order(...)

# After action - verify
verification = gate.verify(
    action_type='transaction',
    target='dhan_orders',
    postconditions=compiled.postconditions,
    post_state=order_result
)

# Generate and store receipt
receipt = generator.generate(
    intent=intent,
    action_type='transaction',
    target='dhan_orders',
    parameters=compiled.parameters,
    verification_result=verification,
    post_state=order_result
)

db.store_receipt(receipt)
print(f"✅ Receipt stored: {receipt.receipt_id}")
```

---

## Troubleshooting

### Issue: `cryptography` package not found

```bash
pip3 install cryptography --break-system-packages
```

### Issue: Ed25519 key generation fails

Ensure you have write permissions in the `keys/` directory:

```bash
mkdir -p keys
chmod 700 keys
python3 vg-cli.py generate-key
```

### Issue: Database locked error

SQLite databases can only be written by one process at a time. Ensure no other process is accessing `receipts.db`.

### Issue: Demo fails with invariant errors

Check that all postconditions match your actual data structure. Update `intent_compiler.py` if needed.

---

## Security Checklist

Before deploying to production:

- [ ] Generate persistent Ed25519 keys (not random)
- [ ] Store private key securely (HSM, secrets manager, or encrypted file)
- [ ] Set restrictive permissions on `keys/private_key.pem` (chmod 600)
- [ ] Distribute public key to all verifiers
- [ ] Enable database encryption if storing sensitive data
- [ ] Set up regular backups of `receipts.db`
- [ ] Configure log rotation for audit logs
- [ ] Review and customize invariant checks for your use case

---

## Next Steps

1. Read [QUICKSTART.md](QUICKSTART.md) for usage examples
2. Review [SPEC.md](SPEC.md) for technical details
3. Run `python3 demo.py` to see the full flow
4. Integrate with your agent using the code examples above

---

**Built with 🦞 by Experto**  
*"The future of honest agents"*
