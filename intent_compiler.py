#!/usr/bin/env python3
"""
Intent Compiler - Converts natural language agent intents into falsifiable postconditions.

This module takes high-level agent intentions and compiles them into structured,
verifiable claims that can be independently validated by the Verification Gate.

Key Principles:
- Postconditions must be falsifiable (can be proven true or false)
- Invariants must be checkable against actual world state
- No ambiguity - every claim must have clear pass/fail criteria
"""

import hashlib
import json
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class Postcondition:
    """A falsifiable claim about the state after an action."""
    invariant_id: str
    claim: str
    expected: str  # Logical expression
    evidence_path: str  # JSON path to check
    critical: bool = True  # If False, it's a warning-level check


@dataclass
class CompiledIntent:
    """Output of the intent compilation process."""
    original_intent: str
    intent_hash: str
    action_type: str
    target: str
    parameters: Dict[str, Any]
    postconditions: List[Postcondition]
    invariants: List[str]  # Human-readable invariant descriptions
    confidence: float  # How confident we are in the compilation (0.0-1.0)
    warnings: List[str]


class IntentCompiler:
    """
    Compiles natural language intents into structured, verifiable postconditions.
    
    Uses pattern matching and heuristics to identify:
    - What action is being taken
    - What the expected outcome should be
    - What invariants must hold true
    """
    
    # Pattern library for common agent actions
    ACTION_PATTERNS = {
        'check_market_status': [
            r'check\s+if\s+market\s+is\s+(open|closed)',
            r'get\s+market\s+status',
            r'is\s+market\s+(open|closed)',
        ],
        'check_position': [
            r'check\s+(my\s+)?position',
            r'get\s+positions?',
            r'list\s+positions?',
            r'how\s+many\s+positions?',
        ],
        'place_order': [
            r'(buy|sell)\s+(\d+)\s+(shares|qty)?\s*of\s+(\w+)',
            r'place\s+(buy|sell)\s+order',
            r'order\s+(\d+)\s+(shares|qty)?\s*(\w+)',
        ],
        'check_pnl': [
            r'check\s+(my\s+)?(p&l|profit|loss|pnl)',
            r'get\s+p&l',
            r'what.*profit',
            r'what.*loss',
        ],
        'api_call': [
            r'call\s+api\s+(\S+)',
            r'fetch\s+from\s+(\S+)',
            r'get\s+data\s+from\s+(\S+)',
        ],
        'file_read': [
            r'read\s+file\s+(\S+)',
            r'load\s+(\S+\.txt|\S+\.json|\S+\.csv)',
        ],
        'file_write': [
            r'write\s+to\s+(\S+)',
            r'save\s+(\S+)',
            r'create\s+file\s+(\S+)',
        ],
    }
    
    def __init__(self):
        self.invariant_counter = 0
    
    def _generate_invariant_id(self) -> str:
        """Generate unique invariant identifier."""
        self.invariant_counter += 1
        return f"INV-{self.invariant_counter:03d}"
    
    def _hash_intent(self, intent: str) -> str:
        """Create SHA-256 hash of the original intent."""
        return hashlib.sha256(intent.encode('utf-8')).hexdigest()
    
    def _detect_action(self, intent: str) -> tuple:
        """Detect action type and target from intent."""
        intent_lower = intent.lower()
        
        for action_type, patterns in self.ACTION_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, intent_lower)
                if match:
                    # Extract parameters from match groups
                    params = {}
                    if action_type == 'place_order':
                        if len(match.groups()) >= 4:
                            params['side'] = match.group(1)
                            params['quantity'] = match.group(2)
                            params['symbol'] = match.group(4) if len(match.groups()) >= 4 else None
                    
                    return action_type, intent_lower.split()[0:3], params
        
        # Default: generic API call
        return 'generic_action', ['unknown'], {}
    
    def _compile_market_status_intent(self, intent: str) -> CompiledIntent:
        """Compile market status checking intents."""
        return CompiledIntent(
            original_intent=intent,
            intent_hash=self._hash_intent(intent),
            action_type='api_call',
            target='https://api.dhan.co/market-status',
            parameters={'endpoint': 'market-status'},
            postconditions=[
                Postcondition(
                    invariant_id=self._generate_invariant_id(),
                    claim="Market status must be a valid state",
                    expected="market_status in ['OPEN', 'CLOSED', 'PRE_OPEN', 'POST_CLOSE']",
                    evidence_path='$.market_status',
                    critical=True
                ),
                Postcondition(
                    invariant_id=self._generate_invariant_id(),
                    claim="Market status timestamp must be recent (within 5 minutes)",
                    expected="abs(now - last_updated) < 300",
                    evidence_path='$.last_updated',
                    critical=False
                )
            ],
            invariants=[
                "Market status is never null",
                "Market status is one of: OPEN, CLOSED, PRE_OPEN, POST_CLOSE"
            ],
            confidence=0.95,
            warnings=[]
        )
    
    def _compile_position_check_intent(self, intent: str) -> CompiledIntent:
        """Compile position checking intents."""
        return CompiledIntent(
            original_intent=intent,
            intent_hash=self._hash_intent(intent),
            action_type='api_call',
            target='https://api.dhan.co/positions',
            parameters={'segment': 'NSE_EQ'},
            postconditions=[
                Postcondition(
                    invariant_id=self._generate_invariant_id(),
                    claim="Positions response must be a valid array",
                    expected="is_array(positions)",
                    evidence_path='$.positions',
                    critical=True
                ),
                Postcondition(
                    invariant_id=self._generate_invariant_id(),
                    claim="Each position must have required fields",
                    expected="all(p.symbol and p.quantity for p in positions)",
                    evidence_path='$.positions[*]',
                    critical=True
                ),
                Postcondition(
                    invariant_id=self._generate_invariant_id(),
                    claim="Total positions count matches array length",
                    expected="total_count == len(positions)",
                    evidence_path='$.total_count',
                    critical=False
                )
            ],
            invariants=[
                "Positions list is never null (empty list if no positions)",
                "All positions have symbol, quantity, and side fields"
            ],
            confidence=0.90,
            warnings=["Position data may be delayed by up to 1 minute"]
        )
    
    def _compile_order_placement_intent(self, intent: str) -> CompiledIntent:
        """Compile order placement intents."""
        # Extract order details using regex
        order_match = re.search(
            r'(buy|sell)\s+(\d+)\s*(?:shares|qty)?\s*(?:of\s+)?(\w+)',
            intent.lower()
        )
        
        params = {}
        if order_match:
            params['side'] = order_match.group(1).upper()
            params['quantity'] = int(order_match.group(2))
            params['symbol'] = order_match.group(3).upper()
        
        return CompiledIntent(
            original_intent=intent,
            intent_hash=self._hash_intent(intent),
            action_type='transaction',
            target='https://api.dhan.co/orders',
            parameters=params,
            postconditions=[
                Postcondition(
                    invariant_id=self._generate_invariant_id(),
                    claim="Order must receive a valid order ID",
                    expected="order_id is not null and len(order_id) > 0",
                    evidence_path='$.order_id',
                    critical=True
                ),
                Postcondition(
                    invariant_id=self._generate_invariant_id(),
                    claim="Order status must be initial state",
                    expected="status in ['PENDING', 'OPEN', 'REJECTED']",
                    evidence_path='$.status',
                    critical=True
                ),
                Postcondition(
                    invariant_id=self._generate_invariant_id(),
                    claim="Order details must match request",
                    expected=f"side == '{params.get('side', 'UNKNOWN')}' and quantity == {params.get('quantity', 0)}",
                    evidence_path='$.order_details',
                    critical=True
                )
            ],
            invariants=[
                "Every order receives an order_id",
                "Order status is set immediately",
                "Order details match the request parameters"
            ],
            confidence=0.85,
            warnings=["Order execution is asynchronous - final status may change"]
        )
    
    def _compile_generic_intent(self, intent: str) -> CompiledIntent:
        """Compile generic intents that don't match specific patterns."""
        action_type, keywords, params = self._detect_action(intent)
        
        return CompiledIntent(
            original_intent=intent,
            intent_hash=self._hash_intent(intent),
            action_type=action_type,
            target='unknown',
            parameters=params,
            postconditions=[
                Postcondition(
                    invariant_id=self._generate_invariant_id(),
                    claim="Action must complete without error",
                    expected="error == null or error.code < 400",
                    evidence_path='$.error',
                    critical=True
                ),
                Postcondition(
                    invariant_id=self._generate_invariant_id(),
                    claim="Response must contain data or explicit empty marker",
                    expected="data != null or explicitly_empty == true",
                    evidence_path='$.data',
                    critical=False
                )
            ],
            invariants=[
                "Actions complete with either success or explicit error",
                "No silent failures - errors are always reported"
            ],
            confidence=0.60,
            warnings=[
                "Generic compilation - may miss domain-specific invariants",
                "Consider adding custom postconditions for this action type"
            ]
        )
    
    def compile(self, intent: str) -> CompiledIntent:
        """
        Compile a natural language intent into structured postconditions.
        
        Args:
            intent: Natural language description of what the agent wants to do
            
        Returns:
            CompiledIntent with postconditions and invariants
        """
        intent_lower = intent.lower()
        
        # Route to specific compilers based on intent patterns
        if any(kw in intent_lower for kw in ['market', 'open', 'closed']):
            return self._compile_market_status_intent(intent)
        elif any(kw in intent_lower for kw in ['position', 'positions', 'holdings']):
            return self._compile_position_check_intent(intent)
        elif any(kw in intent_lower for kw in ['buy', 'sell', 'order']):
            return self._compile_order_placement_intent(intent)
        else:
            return self._compile_generic_intent(intent)
    
    def compile_batch(self, intents: List[str]) -> List[CompiledIntent]:
        """Compile multiple intents at once."""
        return [self.compile(intent) for intent in intents]
    
    def to_json(self, compiled: CompiledIntent) -> str:
        """Convert CompiledIntent to JSON string."""
        return json.dumps(asdict(compiled), indent=2)
    
    def from_json(self, json_str: str) -> CompiledIntent:
        """Parse JSON string back to CompiledIntent."""
        data = json.loads(json_str)
        postconditions = [Postcondition(**pc) for pc in data['postconditions']]
        data['postconditions'] = postconditions
        return CompiledIntent(**data)


# Convenience function for quick compilation
def compile_intent(intent: str) -> CompiledIntent:
    """Quick helper to compile a single intent."""
    compiler = IntentCompiler()
    return compiler.compile(intent)


if __name__ == '__main__':
    # Demo usage
    compiler = IntentCompiler()
    
    test_intents = [
        "Check if market is open",
        "Get my current positions",
        "Buy 100 shares of RELIANCE",
        "What's my P&L today?",
        "Read file config.json",
    ]
    
    print("=" * 60)
    print("INTENT COMPILER DEMO")
    print("=" * 60)
    
    for intent in test_intents:
        print(f"\n📝 Intent: {intent}")
        print("-" * 40)
        compiled = compiler.compile(intent)
        print(f"   Action: {compiled.action_type}")
        print(f"   Target: {compiled.target}")
        print(f"   Confidence: {compiled.confidence:.0%}")
        print(f"   Postconditions: {len(compiled.postconditions)}")
        for pc in compiled.postconditions:
            print(f"      [{pc.invariant_id}] {pc.claim}")
        if compiled.warnings:
            print(f"   Warnings: {len(compiled.warnings)}")
            for w in compiled.warnings:
                print(f"      ⚠️  {w}")
