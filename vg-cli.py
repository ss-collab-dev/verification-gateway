#!/usr/bin/env python3
"""
Verification Gateway CLI - Command-line interface for receipt verification.

Commands:
    verify <receipt_id>   - Verify a receipt by ID
    list                  - List recent receipts
    status                - Show database statistics
    generate-key          - Generate Ed25519 keypair
    search <query>        - Search receipts
    export                - Export all receipts to JSON
"""

import sys
import json
import argparse
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from receipt_db import ReceiptDatabase
from receipt_generator import ReceiptGenerator


def cmd_verify(args):
    """Verify a receipt by ID."""
    db = ReceiptDatabase()
    receipt_data = db.get_receipt(args.receipt_id)
    
    if not receipt_data:
        print(f"❌ Receipt not found: {args.receipt_id}")
        sys.exit(1)
    
    # Reconstruct receipt object for verification
    from receipt_generator import Receipt
    receipt = Receipt(**receipt_data)
    
    # Verify signature
    generator = ReceiptGenerator(algorithm=receipt.signature['algorithm'])
    is_valid = generator.verify_signature(receipt)
    
    print(f"\n🧾 Receipt Verification")
    print(f"   ID: {receipt.receipt_id}")
    print(f"   Timestamp: {receipt.timestamp}")
    print(f"   Intent Hash: {receipt.intent_hash[:32]}...")
    print(f"   Action: {receipt.action_taken['action_type']} → {receipt.action_taken['target']}")
    print(f"   Verification Status: {receipt.verification_result['status']}")
    print(f"   Confidence: {receipt.verification_result['confidence']:.0%}")
    print(f"   Signature Algorithm: {receipt.signature['algorithm']}")
    print(f"   Signature Valid: {'✅ YES' if is_valid else '❌ NO'}")
    
    if receipt.verification_result.get('failed_invariants'):
        print(f"\n   ⚠️  Failed Invariants:")
        for inv_id in receipt.verification_result['failed_invariants']:
            print(f"      - {inv_id}")
    
    sys.exit(0 if is_valid else 1)


def cmd_list(args):
    """List recent receipts."""
    db = ReceiptDatabase()
    
    if args.status:
        receipts = db.get_receipts_by_status(args.status, limit=args.limit)
    elif args.executor:
        receipts = db.get_receipts_by_executor(args.executor, limit=args.limit)
    else:
        receipts = db.get_recent_receipts(hours=args.hours, limit=args.limit)
    
    if not receipts:
        print("📭 No receipts found")
        sys.exit(0)
    
    print(f"\n📋 Recent Receipts ({len(receipts)} found)")
    print("-" * 80)
    
    for r in receipts:
        status_icon = "✅" if r['verification_result']['status'] == 'PASS' else "⚠️"
        print(f"{status_icon} [{r['receipt_id'][:8]}...] {r['verification_result']['status']:10} | "
              f"{r['action_taken']['action_type']:15} | {r['timestamp'][:19]}")
        
        if args.verbose:
            print(f"   Intent: {r['intent_hash'][:32]}...")
            print(f"   Executor: {r['action_taken']['executor_id']}")
            print(f"   Signature: {r['signature']['algorithm']}")
            print()
    
    print("-" * 80)


def cmd_status(args):
    """Show database statistics."""
    db = ReceiptDatabase()
    stats = db.get_statistics()
    
    print(f"\n📊 Verification Gateway Statistics")
    print("=" * 50)
    print(f"Database: {stats['database_path']}")
    print(f"\nTotal Receipts: {stats['total_receipts']}")
    print(f"Last 24 Hours: {stats['last_24_hours']}")
    
    if stats['by_status']:
        print(f"\nBy Status:")
        for status, count in stats['by_status'].items():
            icon = "✅" if status == 'PASS' else "⚠️" if status == 'PARTIAL' else "❌"
            print(f"   {icon} {status}: {count}")
    
    if stats['top_executors']:
        print(f"\nTop Executors:")
        for executor, count in list(stats['top_executors'].items())[:5]:
            print(f"   - {executor}: {count} receipts")


def cmd_generate_key(args):
    """Generate Ed25519 keypair."""
    keys_dir = Path(__file__).parent / 'keys'
    keys_dir.mkdir(exist_ok=True)
    
    private_path = keys_dir / 'private_key.pem'
    public_path = keys_dir / 'public_key.pem'
    
    # Remove existing keys if forced
    if args.force and private_path.exists():
        private_path.unlink()
    if args.force and public_path.exists():
        public_path.unlink()
    
    # Generate new keys
    generator = ReceiptGenerator(
        algorithm="Ed25519",
        private_key_path=str(private_path) if not private_path.exists() else None,
        public_key_path=str(public_path) if not public_path.exists() else None
    )
    
    if generator.algorithm == "Ed25519":
        print(f"\n✅ Ed25519 Keypair Generated")
        print(f"   Private Key: {private_path}")
        print(f"   Public Key:  {public_path}")
        print(f"\n⚠️  IMPORTANT: Keep your private key secure!")
        print(f"   Never share it or commit it to version control.")
    else:
        print(f"\n❌ Failed to generate Ed25519 keys")
        print(f"   Install cryptography package: pip install cryptography")
        sys.exit(1)


def cmd_search(args):
    """Search receipts."""
    db = ReceiptDatabase()
    results = db.search_receipts(args.query, limit=args.limit)
    
    if not results:
        print(f"📭 No receipts matching: {args.query}")
        sys.exit(0)
    
    print(f"\n🔍 Search Results for '{args.query}' ({len(results)} found)")
    print("-" * 80)
    
    for r in results:
        status_icon = "✅" if r['verification_result']['status'] == 'PASS' else "⚠️"
        print(f"{status_icon} [{r['receipt_id'][:8]}...] {r['verification_result']['status']:10} | "
              f"{r['action_taken']['action_type']:15} | {r['timestamp'][:19]}")


def cmd_export(args):
    """Export all receipts to JSON."""
    db = ReceiptDatabase()
    receipts = db.export_all()
    
    output_path = args.output or Path(__file__).parent / 'receipts-export.json'
    
    with open(output_path, 'w') as f:
        json.dump(receipts, f, indent=2)
    
    print(f"\n✅ Exported {len(receipts)} receipts to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        prog='vg-cli',
        description='Verification Gateway CLI - Receipt verification and management'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # verify command
    verify_parser = subparsers.add_parser('verify', help='Verify a receipt by ID')
    verify_parser.add_argument('receipt_id', help='Receipt UUID to verify')
    verify_parser.set_defaults(func=cmd_verify)
    
    # list command
    list_parser = subparsers.add_parser('list', help='List recent receipts')
    list_parser.add_argument('--limit', '-n', type=int, default=20, help='Max receipts to show')
    list_parser.add_argument('--hours', type=int, default=24, help='Time window in hours')
    list_parser.add_argument('--status', '-s', choices=['PASS', 'FAIL', 'PARTIAL', 'UNVERIFIED'],
                            help='Filter by verification status')
    list_parser.add_argument('--executor', '-e', help='Filter by executor ID')
    list_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed info')
    list_parser.set_defaults(func=cmd_list)
    
    # status command
    status_parser = subparsers.add_parser('status', help='Show database statistics')
    status_parser.set_defaults(func=cmd_status)
    
    # generate-key command
    key_parser = subparsers.add_parser('generate-key', help='Generate Ed25519 keypair')
    key_parser.add_argument('--force', '-f', action='store_true', help='Overwrite existing keys')
    key_parser.set_defaults(func=cmd_generate_key)
    
    # search command
    search_parser = subparsers.add_parser('search', help='Search receipts')
    search_parser.add_argument('query', help='Search term')
    search_parser.add_argument('--limit', '-n', type=int, default=50, help='Max results')
    search_parser.set_defaults(func=cmd_search)
    
    # export command
    export_parser = subparsers.add_parser('export', help='Export all receipts to JSON')
    export_parser.add_argument('--output', '-o', help='Output file path')
    export_parser.set_defaults(func=cmd_export)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == '__main__':
    main()
