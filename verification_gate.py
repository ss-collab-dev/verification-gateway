#!/usr/bin/env python3
"""
Verification Gate - Independent verification of agent actions against claimed postconditions.

This module provides the critical security layer: it independently reads world state
and verifies that the agent's claimed outcomes actually match reality.

Key Principles:
- ZERO shared state with the execution layer
- All state reads happen AFTER action completion
- Evidence is captured and included in verification result
- Falsifiable: every check can definitively PASS or FAIL
"""

import json
import hashlib
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class InvariantResult:
    """Result of a single invariant check."""
    invariant_id: str
    claim: str
    expected: str
    actual: str
    passed: bool
    evidence_path: str
    evidence_value: Any
    error: Optional[str] = None


@dataclass
class VerificationResult:
    """Complete verification result for an action."""
    status: str  # PASS, FAIL, PARTIAL, UNVERIFIED
    confidence: float  # 0.0 to 1.0
    verified_by: str
    timestamp: str
    invariant_results: List[InvariantResult]
    failed_invariants: List[str]
    warnings: List[str]
    pre_state: Optional[Dict[str, Any]] = None
    post_state: Optional[Dict[str, Any]] = None
    raw_evidence: Optional[Dict[str, Any]] = None


class StateReader:
    """
    Independent state reader - NO shared state with execution layer.
    
    This class is responsible for reading actual world state from various sources.
    Each read operation is independent and captures a timestamped snapshot.
    """
    
    def __init__(self, state_sources: Optional[Dict[str, Callable]] = None):
        """
        Initialize with state source functions.
        
        Args:
            state_sources: Dict mapping source names to reader functions.
                          Each function should return (data, timestamp) tuple.
        """
        self.state_sources = state_sources or {}
        self.read_log = []  # Internal log for audit trail
    
    def register_source(self, name: str, reader_fn: Callable):
        """Register a new state source."""
        self.state_sources[name] = reader_fn
    
    def read(self, source: str, method: str = 'api_get', params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Read state from a source independently.
        
        Args:
            source: Source identifier (e.g., 'dhan_positions', 'market_status')
            method: Read method (api_get, file_read, database_query)
            params: Optional parameters for the read
            
        Returns:
            Dict with 'data', 'timestamp', 'source', 'method'
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Try to use registered source
        if source in self.state_sources:
            try:
                reader_fn = self.state_sources[source]
                data = reader_fn(params) if params else reader_fn()
                
                read_result = {
                    'data': data,
                    'timestamp': timestamp,
                    'source': source,
                    'method': method
                }
                
                # Log for audit
                self.read_log.append({
                    'timestamp': timestamp,
                    'source': source,
                    'method': method,
                    'success': True
                })
                
                return read_result
                
            except Exception as e:
                self.read_log.append({
                    'timestamp': timestamp,
                    'source': source,
                    'method': method,
                    'success': False,
                    'error': str(e)
                })
                raise
        
        # If source not registered, return placeholder for demo
        return {
            'data': {'error': f'Unknown source: {source}'},
            'timestamp': timestamp,
            'source': source,
            'method': method
        }
    
    def get_read_log(self) -> List[Dict[str, Any]]:
        """Get audit log of all state reads."""
        return self.read_log.copy()


class InvariantChecker:
    """
    Evaluates postconditions against actual state.
    
    Supports simple logical expressions for falsifiable claims.
    """
    
    def __init__(self):
        self.check_log = []
    
    def _extract_value(self, data: Dict[str, Any], path: str) -> Any:
        """
        Extract value from nested dict using JSON path-like syntax.
        
        Args:
            data: Dictionary to extract from
            path: Path like '$.market_status' or '$.positions[0].symbol'
            
        Returns:
            Extracted value or None if path invalid
        """
        if not path.startswith('$'):
            return None
        
        # Remove leading $ and split
        parts = path.lstrip('$').lstrip('.').split('.')
        current = data
        
        for part in parts:
            if current is None:
                return None
            
            # Handle array indexing
            array_match = re.match(r'(\w+)\[(\d+)\]', part)
            if array_match:
                key = array_match.group(1)
                index = int(array_match.group(2))
                if isinstance(current, dict) and key in current:
                    current = current[key]
                    if isinstance(current, list) and 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None
                else:
                    return None
            elif isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        
        return current
    
    def _evaluate_expression(self, expression: str, context: Dict[str, Any]) -> bool:
        """
        Safely evaluate a logical expression.
        
        Args:
            expression: Logical expression like "market_status in ['OPEN', 'CLOSED']"
            context: Variables available for evaluation
            
        Returns:
            Boolean result
        """
        try:
            # Safe evaluation using restricted namespace
            # Only allow basic operations
            safe_globals = {
                '__builtins__': {},
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                'is_array': lambda x: isinstance(x, list),
                'is_null': lambda x: x is None,
                'abs': abs,
                'all': lambda gen: all(gen),
                'any': lambda gen: any(gen),
                'null': None,
                'none': None,
                'isinstance': isinstance,  # Allow isinstance for type checks
                'list': list,  # Allow list type for isinstance
                'dict': dict,  # Allow dict type for isinstance
                'now': datetime.now(timezone.utc).timestamp(),  # Current timestamp
                'str': str,    # Allow str type for isinstance
                'int': int,    # Allow int type for isinstance
                'float': float,# Allow float type for isinstance
            }
            
            # Create local context from extracted values
            safe_locals = context.copy()
            
            # Handle array iteration patterns like "all(p.symbol and p.quantity for p in positions)"
            # Pre-evaluate generator expressions
            import re
            all_match = re.match(r'all\((.+)\s+for\s+(\w+)\s+in\s+(\w+)\)', expression)
            if all_match:
                condition = all_match.group(1)
                var_name = all_match.group(2)
                list_name = all_match.group(3)
                
                if list_name not in safe_locals:
                    raise ValueError(f"List '{list_name}' not found in context")
                
                items = safe_locals[list_name]
                if not isinstance(items, list):
                    return False
                
                # Evaluate condition for each item
                results = []
                for item in items:
                    if isinstance(item, dict):
                        item_context = safe_globals.copy()
                        item_context.update(safe_locals)
                        # Flatten item fields into context with 'p.' prefix for variable access
                        item_context[var_name] = item
                        # Also add direct field access
                        for k, v in item.items():
                            item_context[k] = v
                        try:
                            results.append(eval(condition, item_context, item_context))
                        except Exception as ex:
                            # Try simpler evaluation where p.symbol means item['symbol']
                            try:
                                # Replace p.field with item['field'] pattern
                                cond_simple = condition.replace(f'{var_name}.', '')
                                results.append(eval(cond_simple, safe_globals, item))
                            except:
                                results.append(False)
                    else:
                        # Simple value comparison
                        item_context = safe_globals.copy()
                        item_context.update(safe_locals)
                        item_context[var_name] = item
                        try:
                            results.append(eval(condition, item_context, item_context))
                        except:
                            results.append(False)
                
                return all(results) if results else False
            
            # Handle any() pattern similarly
            any_match = re.match(r'any\((.+)\s+for\s+(\w+)\s+in\s+(\w+)\)', expression)
            if any_match:
                condition = any_match.group(1)
                var_name = any_match.group(2)
                list_name = any_match.group(3)
                
                if list_name not in safe_locals:
                    return False
                
                items = safe_locals[list_name]
                if not isinstance(items, list):
                    return False
                
                for item in items:
                    if isinstance(item, dict):
                        item_context = safe_locals.copy()
                        for k, v in item.items():
                            item_context[k] = v
                        try:
                            if eval(condition, safe_globals, item_context):
                                return True
                        except:
                            continue
                    else:
                        item_context = safe_locals.copy()
                        item_context[var_name] = item
                        try:
                            if eval(condition, safe_globals, item_context):
                                return True
                        except:
                            continue
                
                return False
            
            # Handle equality comparisons with == operator
            if '==' in expression:
                parts = expression.split('==')
                if len(parts) == 2:
                    left = eval(parts[0].strip(), safe_globals, safe_locals)
                    right = eval(parts[1].strip(), safe_globals, safe_locals)
                    return left == right
            
            # Evaluate
            result = eval(expression, safe_globals, safe_locals)
            return bool(result)
            
        except Exception as e:
            raise ValueError(f"Expression evaluation failed: {expression} - {str(e)}")
    
    def check_invariant(
        self,
        invariant_id: str,
        claim: str,
        expected: str,
        evidence_path: str,
        state_data: Dict[str, Any]
    ) -> InvariantResult:
        """
        Check a single invariant against actual state.
        
        Args:
            invariant_id: Unique identifier for this check
            claim: Human-readable description
            expected: Logical expression to evaluate
            evidence_path: JSON path to the evidence
            state_data: Actual state data
            
        Returns:
            InvariantResult with pass/fail and evidence
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        try:
            # Handle wildcard paths like $.positions[*]
            if '[*]' in evidence_path:
                # Extract the array itself
                base_path = evidence_path.replace('[*]', '')
                actual_value = self._extract_value(state_data, base_path)
                
                # Build context with the array
                var_name = base_path.split('.')[-1].split('[')[0]
                context = {var_name: actual_value}
                
                # Add positions to context for array iteration expressions
                if var_name == 'positions':
                    context['positions'] = actual_value
            else:
                # Extract actual value
                actual_value = self._extract_value(state_data, evidence_path)
                
                # Build context for evaluation
                # Extract variable name from path (last component)
                var_name = evidence_path.split('.')[-1].split('[')[0]
                context = {var_name: actual_value}
                
                # ALWAYS add full state data for cross-field comparisons
                context.update(state_data)
                
                # Also add common variables explicitly
                if 'market_status' in state_data:
                    context['market_status'] = state_data['market_status']
                if 'positions' in state_data:
                    context['positions'] = state_data['positions']
                if 'order_id' in state_data:
                    context['order_id'] = state_data['order_id']
                if 'status' in state_data:
                    context['status'] = state_data['status']
                if 'quantity' in state_data:
                    context['quantity'] = state_data['quantity']
                if 'side' in state_data:
                    context['side'] = state_data['side']
                if 'total_count' in state_data:
                    context['total_count'] = state_data['total_count']
            
            # Format actual value for reporting
            actual_str = f"{var_name} = {repr(actual_value)}"
            
            # Evaluate expression
            passed = self._evaluate_expression(expected, context)
            
            result = InvariantResult(
                invariant_id=invariant_id,
                claim=claim,
                expected=expected,
                actual=actual_str,
                passed=passed,
                evidence_path=evidence_path,
                evidence_value=actual_value
            )
            
            self.check_log.append({
                'timestamp': timestamp,
                'invariant_id': invariant_id,
                'passed': passed
            })
            
            return result
            
        except Exception as e:
            result = InvariantResult(
                invariant_id=invariant_id,
                claim=claim,
                expected=expected,
                actual="ERROR",
                passed=False,
                evidence_path=evidence_path,
                evidence_value=None,
                error=str(e)
            )
            
            self.check_log.append({
                'timestamp': timestamp,
                'invariant_id': invariant_id,
                'passed': False,
                'error': str(e)
            })
            
            return result
    
    def get_check_log(self) -> List[Dict[str, Any]]:
        """Get audit log of all invariant checks."""
        return self.check_log.copy()


class VerificationGate:
    """
    Main verification gate - orchestrates state reading and invariant checking.
    
    This is the independent verifier that ensures agents cannot lie about their actions.
    """
    
    VERSION = "verification-gate-v1.0.0"
    
    def __init__(self, state_reader: Optional[StateReader] = None):
        """
        Initialize verification gate.
        
        Args:
            state_reader: Independent state reader (created fresh, no shared state)
        """
        self.state_reader = state_reader or StateReader()
        self.invariant_checker = InvariantChecker()
    
    def verify(
        self,
        action_type: str,
        target: str,
        postconditions: List[Any],  # List of Postcondition objects
        pre_state: Optional[Dict[str, Any]] = None,
        post_state: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 30.0
    ) -> VerificationResult:
        """
        Verify an action against its claimed postconditions.
        
        Args:
            action_type: Type of action (api_call, transaction, etc.)
            target: Target system/resource
            postconditions: List of Postcondition objects to verify
            pre_state: Optional pre-action state snapshot
            post_state: Optional post-action state snapshot (if already captured)
            timeout_seconds: Max time for verification
            
        Returns:
            VerificationResult with PASS/FAIL and evidence
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Capture fresh post-state if not provided
        if post_state is None:
            try:
                state_snapshot = self.state_reader.read(target, 'api_get')
                post_state = state_snapshot['data']
            except Exception as e:
                return VerificationResult(
                    status='UNVERIFIED',
                    confidence=0.0,
                    verified_by=self.VERSION,
                    timestamp=timestamp,
                    invariant_results=[],
                    failed_invariants=[],
                    warnings=[f"Could not read post-state: {str(e)}"],
                    pre_state=pre_state,
                    post_state=None
                )
        
        # Check each postcondition
        results = []
        failed_ids = []
        warnings = []
        
        for pc in postconditions:
            result = self.invariant_checker.check_invariant(
                invariant_id=pc.invariant_id,
                claim=pc.claim,
                expected=pc.expected,
                evidence_path=pc.evidence_path,
                state_data=post_state
            )
            results.append(result)
            
            if not result.passed:
                failed_ids.append(pc.invariant_id)
                if pc.critical:
                    warnings.append(f"Critical invariant failed: {pc.claim}")
        
        # Determine overall status
        if not results:
            status = 'UNVERIFIED'
            confidence = 0.0
        elif len(failed_ids) == 0:
            status = 'PASS'
            confidence = 1.0
        elif len(failed_ids) == len(results):
            status = 'FAIL'
            confidence = 0.0
        else:
            status = 'PARTIAL'
            # Weight by criticality
            critical_total = sum(1 for pc in postconditions if pc.critical)
            critical_failed = sum(
                1 for r in results 
                if not r.passed and next((pc.critical for pc in postconditions if pc.invariant_id == r.invariant_id), False)
            )
            confidence = 1.0 - (critical_failed / critical_total if critical_total > 0 else 0.5)
        
        return VerificationResult(
            status=status,
            confidence=confidence,
            verified_by=self.VERSION,
            timestamp=timestamp,
            invariant_results=results,
            failed_invariants=failed_ids,
            warnings=warnings,
            pre_state=pre_state,
            post_state=post_state,
            raw_evidence=post_state
        )
    
    def verify_with_mock_state(
        self,
        postconditions: List[Any],
        mock_post_state: Dict[str, Any]
    ) -> VerificationResult:
        """
        Verify against mock state (for testing/demo purposes).
        
        Args:
            postconditions: List of Postcondition objects
            mock_post_state: Simulated state data
            
        Returns:
            VerificationResult
        """
        return self.verify(
            action_type='mock',
            target='mock://test',
            postconditions=postconditions,
            post_state=mock_post_state
        )


# Convenience function
def verify_action(postconditions, post_state) -> VerificationResult:
    """Quick helper to verify an action."""
    gate = VerificationGate()
    return gate.verify_with_mock_state(postconditions, post_state)


if __name__ == '__main__':
    # Demo usage
    from intent_compiler import IntentCompiler, Postcondition
    
    print("=" * 60)
    print("VERIFICATION GATE DEMO")
    print("=" * 60)
    
    # Compile an intent
    compiler = IntentCompiler()
    compiled = compiler.compile("Check if market is open")
    
    print(f"\n📋 Compiled Intent:")
    print(f"   Action: {compiled.action_type}")
    print(f"   Postconditions: {len(compiled.postconditions)}")
    
    # Create mock state (simulating what we'd read from Dhan API)
    mock_market_state = {
        'market_status': 'OPEN',
        'last_updated': '2026-05-27T09:15:00Z',
        'segment': 'NSE_EQ'
    }
    
    print(f"\n🔍 Mock State: {json.dumps(mock_market_state, indent=2)}")
    
    # Verify
    gate = VerificationGate()
    result = gate.verify_with_mock_state(compiled.postconditions, mock_market_state)
    
    print(f"\n✅ Verification Result:")
    print(f"   Status: {result.status}")
    print(f"   Confidence: {result.confidence:.0%}")
    print(f"   Verified by: {result.verified_by}")
    print(f"\n   Invariant Checks:")
    for inv_result in result.invariant_results:
        status_icon = "✅" if inv_result.passed else "❌"
        print(f"      {status_icon} [{inv_result.invariant_id}] {inv_result.claim}")
        print(f"          Expected: {inv_result.expected}")
        print(f"          Actual: {inv_result.actual}")
    
    if result.warnings:
        print(f"\n   ⚠️  Warnings:")
        for w in result.warnings:
            print(f"      - {w}")
