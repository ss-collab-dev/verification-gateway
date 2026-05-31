#!/usr/bin/env python3
"""
Verification Gateway - Integration Demo

Demonstrates the complete flow from intent to signed receipt:
1. Agent expresses intent in natural language
2. Intent Compiler creates falsifiable postconditions
3. Execution Layer performs action (simulated)
4. Verification Gate independently validates outcome
5. Receipt Generator creates signed, replayable proof

This demo uses the Dhan Trading API context from the research findings.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from intent_compiler import IntentCompiler, CompiledIntent
from verification_gate import VerificationGate, StateReader
from receipt_generator import ReceiptGenerator, Receipt


def simulate_dhan_api_call(endpoint: str, params: dict = None) -> dict:
    """
    Simulate a Dhan API call for demo purposes.
    
    In production, this would be the actual Execution Layer making real API calls.
    For this demo, we return realistic mock data.
    """
    mock_responses = {
        'market-status': {
            'market_status': 'OPEN',
            'last_updated': '2026-05-27T09:15:00Z',
            'segment': 'NSE_EQ',
            'next_state_change': '2026-05-27T15:30:00Z'
        },
        'positions': {
            'positions': [
                {
                    'symbol': 'RELIANCE',
                    'quantity': 50,
                    'side': 'BUY',
                    'avg_price': 2450.00,
                    'ltp': 2480.50,
                    'pnl': 1525.00
                },
                {
                    'symbol': 'INFY',
                    'quantity': 100,
                    'side': 'BUY',
                    'avg_price': 1420.00,
                    'ltp': 1445.75,
                    'pnl': 2575.00
                }
            ],
            'total_count': 2,
            'total_pnl': 4100.00
        },
        'orders': {
            'order_id': 'DHN202605270001234',
            'status': 'OPEN',
            'symbol': 'TATAMOTORS',
            'side': 'BUY',
            'quantity': 200,
            'price': 985.00,
            'order_type': 'LIMIT',
            'created_at': '2026-05-27T10:30:15Z'
        }
    }
    
    return mock_responses.get(endpoint, {'error': f'Unknown endpoint: {endpoint}'})


def create_dhan_state_reader() -> StateReader:
    """
    Create a state reader configured for Dhan API endpoints.
    
    This is the INDEPENDENT reader used by the Verification Gate.
    It has NO shared state with the Execution Layer.
    """
    reader = StateReader()
    
    # Register Dhan API state sources
    reader.register_source('dhan_market_status', lambda p: simulate_dhan_api_call('market-status'))
    reader.register_source('dhan_positions', lambda p: simulate_dhan_api_call('positions'))
    reader.register_source('dhan_orders', lambda p: simulate_dhan_api_call('orders'))
    
    return reader


def demo_market_status_check():
    """Demo: Agent checks if market is open."""
    print("\n" + "=" * 70)
    print("DEMO 1: Market Status Check")
    print("=" * 70)
    
    # Step 1: Agent expresses intent
    intent = "Check if market is open"
    print(f"\n🤖 Agent Intent: \"{intent}\"")
    
    # Step 2: Compile intent to postconditions
    compiler = IntentCompiler()
    compiled = compiler.compile(intent)
    
    print(f"\n📋 Compiled Postconditions:")
    print(f"   Action Type: {compiled.action_type}")
    print(f"   Target: {compiled.target}")
    print(f"   Intent Hash: {compiled.intent_hash[:32]}...")
    for pc in compiled.postconditions:
        print(f"   [{pc.invariant_id}] {pc.claim}")
        print(f"       Expected: {pc.expected}")
    
    # Step 3: Execution Layer performs action (simulated)
    print(f"\n⚡ Execution Layer: Calling Dhan API...")
    execution_result = simulate_dhan_api_call('market-status')
    print(f"   Response: market_status = {execution_result['market_status']}")
    
    # Step 4: Verification Gate independently reads state
    print(f"\n🔍 Verification Gate: Reading state independently...")
    gate = VerificationGate(create_dhan_state_reader())
    verification = gate.verify(
        action_type=compiled.action_type,
        target='dhan_market_status',
        postconditions=compiled.postconditions,
        post_state=execution_result
    )
    
    print(f"   Status: {verification.status}")
    print(f"   Confidence: {verification.confidence:.0%}")
    for inv in verification.invariant_results:
        icon = "✅" if inv.passed else "❌"
        print(f"   {icon} [{inv.invariant_id}] {inv.actual}")
    
    # Step 5: Generate signed receipt
    print(f"\n🧾 Generating Signed Receipt...")
    generator = ReceiptGenerator()
    receipt = generator.generate(
        intent=intent,
        action_type=compiled.action_type,
        target=compiled.target,
        parameters=compiled.parameters,
        verification_result=verification,
        post_state=execution_result,
        session_id="agent:main:telegram:direct:1388143890",
        metadata={
            'executor_id': 'experto-trading',
            'host': 'osboxes',
            'os': 'linux',
            'runtime': 'python-3.x'
        }
    )
    
    print(f"   Receipt ID: {receipt.receipt_id}")
    print(f"   Signature: {receipt.signature['algorithm']}")
    print(f"   Valid: {generator.verify_signature(receipt)}")
    
    return receipt


def demo_position_check():
    """Demo: Agent checks current positions."""
    print("\n" + "=" * 70)
    print("DEMO 2: Position Check with P&L Verification")
    print("=" * 70)
    
    intent = "Get my current positions and P&L"
    print(f"\n🤖 Agent Intent: \"{intent}\"")
    
    compiler = IntentCompiler()
    compiled = compiler.compile(intent)
    
    print(f"\n📋 Compiled Postconditions:")
    for pc in compiled.postconditions:
        print(f"   [{pc.invariant_id}] {pc.claim}")
    
    # Execution
    print(f"\n⚡ Execution Layer: Fetching positions from Dhan...")
    execution_result = simulate_dhan_api_call('positions')
    print(f"   Found {execution_result['total_count']} positions")
    print(f"   Total P&L: ₹{execution_result['total_pnl']:.2f}")
    
    # Verification
    print(f"\n🔍 Verification Gate: Validating response structure...")
    gate = VerificationGate(create_dhan_state_reader())
    verification = gate.verify(
        action_type=compiled.action_type,
        target='dhan_positions',
        postconditions=compiled.postconditions,
        post_state=execution_result
    )
    
    print(f"   Status: {verification.status}")
    for inv in verification.invariant_results:
        icon = "✅" if inv.passed else "❌"
        print(f"   {icon} [{inv.invariant_id}] {inv.passed}")
    
    # Receipt
    generator = ReceiptGenerator()
    receipt = generator.generate(
        intent=intent,
        action_type=compiled.action_type,
        target=compiled.target,
        parameters=compiled.parameters,
        verification_result=verification,
        post_state=execution_result,
        session_id="agent:main:telegram:direct:1388143890",
        metadata={'executor_id': 'experto-trading'}
    )
    
    print(f"\n🧾 Receipt: {receipt.receipt_id[:8]}... | Valid: {generator.verify_signature(receipt)}")
    
    return receipt


def demo_order_placement():
    """Demo: Agent places a buy order."""
    print("\n" + "=" * 70)
    print("DEMO 3: Order Placement Verification")
    print("=" * 70)
    
    intent = "Buy 200 shares of TATAMOTORS at 985"
    print(f"\n🤖 Agent Intent: \"{intent}\"")
    
    compiler = IntentCompiler()
    compiled = compiler.compile(intent)
    
    print(f"\n📋 Order Parameters:")
    print(f"   Side: {compiled.parameters.get('side')}")
    print(f"   Quantity: {compiled.parameters.get('quantity')}")
    print(f"   Symbol: {compiled.parameters.get('symbol')}")
    
    print(f"\n📋 Postconditions:")
    for pc in compiled.postconditions:
        print(f"   [{pc.invariant_id}] {pc.claim}")
    
    # Execution
    print(f"\n⚡ Execution Layer: Placing order with Dhan...")
    execution_result = simulate_dhan_api_call('orders')
    print(f"   Order ID: {execution_result['order_id']}")
    print(f"   Status: {execution_result['status']}")
    
    # Verification
    print(f"\n🔍 Verification Gate: Confirming order was placed...")
    gate = VerificationGate(create_dhan_state_reader())
    verification = gate.verify(
        action_type='transaction',
        target='dhan_orders',
        postconditions=compiled.postconditions,
        post_state=execution_result
    )
    
    print(f"   Status: {verification.status}")
    for inv in verification.invariant_results:
        icon = "✅" if inv.passed else "❌"
        print(f"   {icon} [{inv.invariant_id}] {inv.actual}")
    
    # Receipt
    generator = ReceiptGenerator()
    receipt = generator.generate(
        intent=intent,
        action_type='transaction',
        target=compiled.target,
        parameters=compiled.parameters,
        verification_result=verification,
        post_state=execution_result,
        session_id="agent:main:telegram:direct:1388143890",
        metadata={
            'executor_id': 'experto-trading',
            'order_type': 'live_trade'
        }
    )
    
    print(f"\n🧾 Trade Receipt: {receipt.receipt_id[:8]}...")
    print(f"   Signature Valid: {generator.verify_signature(receipt)}")
    
    # Save receipt to file
    receipt_path = Path(__file__).parent / f"receipt-{receipt.receipt_id[:8]}.json"
    generator.save_receipt(receipt, str(receipt_path))
    print(f"   Saved to: {receipt_path.name}")
    
    return receipt


def demo_failed_verification():
    """Demo: Show what happens when verification fails."""
    print("\n" + "=" * 70)
    print("DEMO 4: Failed Verification (Tampered Data)")
    print("=" * 70)
    
    intent = "Check if market is open"
    print(f"\n🤖 Agent Intent: \"{intent}\"")
    
    compiler = IntentCompiler()
    compiled = compiler.compile(intent)
    
    # Tampered state (agent lying about market status)
    tampered_state = {
        'market_status': 'UNKNOWN',  # Invalid value!
        'last_updated': '2026-05-27T09:15:00Z'
    }
    
    print(f"\n⚠️  Agent Claims: market_status = {tampered_state['market_status']}")
    
    # Verification will fail
    gate = VerificationGate()
    verification = gate.verify_with_mock_state(compiled.postconditions, tampered_state)
    
    print(f"\n🔍 Verification Gate: {verification.status}")
    for inv in verification.invariant_results:
        icon = "✅" if inv.passed else "❌"
        print(f"   {icon} [{inv.invariant_id}] Expected: {inv.expected}")
        print(f"                   Actual: {inv.actual}")
    
    # Receipt still generated (showing the failure)
    generator = ReceiptGenerator()
    receipt = generator.generate(
        intent=intent,
        action_type=compiled.action_type,
        target=compiled.target,
        parameters=compiled.parameters,
        verification_result=verification,
        post_state=tampered_state,
        session_id="agent:main:telegram:direct:1388143890",
        metadata={'executor_id': 'suspicious-agent'}
    )
    
    print(f"\n🧾 Receipt Generated (documenting the failure):")
    print(f"   Status: {receipt.verification_result['status']}")
    print(f"   Failed Invariants: {receipt.verification_result['failed_invariants']}")
    print(f"   This receipt proves the agent's claim was INVALID")
    
    return receipt


def main():
    """Run all demos."""
    print("\n" + "🦞" * 35)
    print("VERIFICATION GATEWAY - INTEGRATION DEMO")
    print("Receipt-Based Verification for Honest Agents")
    print("🦞" * 35)
    
    receipts = []
    
    # Run demos
    receipts.append(demo_market_status_check())
    receipts.append(demo_position_check())
    receipts.append(demo_order_placement())
    receipts.append(demo_failed_verification())
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n✅ Generated {len(receipts)} receipts")
    print(f"   - Market status check: {receipts[0].receipt_id[:8]}...")
    print(f"   - Position check: {receipts[1].receipt_id[:8]}...")
    print(f"   - Order placement: {receipts[2].receipt_id[:8]}...")
    print(f"   - Failed verification: {receipts[3].receipt_id[:8]}...")
    
    print(f"\n🔐 All receipts are:")
    print(f"   - Cryptographically signed")
    print(f"   - Replayable (can be independently verified)")
    print(f"   - Falsifiable (prove what actually happened)")
    
    print(f"\n📁 Output Files:")
    output_dir = Path(__file__).parent
    for f in sorted(output_dir.glob('*')):
        if f.is_file():
            print(f"   - {f.name}")
    
    print("\n" + "🦞" * 35)
    print("DEMO COMPLETE - The future of honest agents is here!")
    print("🦞" * 35 + "\n")


if __name__ == '__main__':
    main()
