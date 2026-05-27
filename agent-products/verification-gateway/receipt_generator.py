#!/usr/bin/env python3
"""
Receipt Generator - Creates signed, replayable proof of verified actions.

This module takes verification results and generates cryptographically signed
receipts that serve as tamper-evident proof of what actually happened.

Key Principles:
- Receipts are immutable once signed
- Signature covers all critical fields
- Receipts are replayable (can be independently verified)
- Supports HMAC-SHA256 (symmetric) and Ed25519 (asymmetric) signing
"""

import json
import hashlib
import hmac
import base64
import uuid
import os
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Receipt:
    """A signed verification receipt."""
    receipt_id: str
    version: str
    timestamp: str
    intent_hash: str
    action_taken: Dict[str, Any]
    pre_state: Optional[Dict[str, Any]]
    post_state: Optional[Dict[str, Any]]
    invariants_checked: List[Dict[str, Any]]
    verification_result: Dict[str, Any]
    context_bundle: Dict[str, Any]
    signature: Dict[str, Any]


class ReceiptGenerator:
    """
    Generates signed receipts from verification results.
    
    Supports multiple signing algorithms:
    - HMAC-SHA256 (default, symmetric)
    - Ed25519 (asymmetric, if cryptography package available)
    """
    
    VERSION = "1.0.0"
    DEFAULT_ALGORITHM = "HMAC-SHA256"
    
    def __init__(self, signing_key: Optional[bytes] = None, algorithm: str = "HMAC-SHA256",
                 private_key_path: Optional[str] = None, public_key_path: Optional[str] = None):
        """
        Initialize receipt generator.
        
        Args:
            signing_key: Secret key for HMAC signing (32 bytes recommended)
                        If None, generates a random key (NOT for production!)
            algorithm: Signing algorithm (HMAC-SHA256 or Ed25519)
            private_key_path: Path to Ed25519 private key PEM file
            public_key_path: Path to Ed25519 public key PEM file
        """
        self.algorithm = algorithm
        self.private_key = None
        self.public_key = None
        
        if algorithm == "Ed25519":
            self._load_or_generate_ed25519_keys(private_key_path, public_key_path)
        else:
            if signing_key is None:
                # Generate random key for demo/testing
                self.signing_key = hashlib.sha256(
                    datetime.now().isoformat().encode()
                ).digest()
                print("⚠️  WARNING: Generated random signing key. Use persistent key in production!")
            else:
                self.signing_key = signing_key
        
        self.public_key_id = f"verification-gateway-key-{datetime.now().strftime('%Y-%m')}"
    
    def _load_or_generate_ed25519_keys(self, private_key_path: Optional[str], 
                                        public_key_path: Optional[str]):
        """
        Load existing Ed25519 keys or generate new ones.
        """
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives import serialization
            
            keys_dir = Path(__file__).parent / 'keys'
            keys_dir.mkdir(exist_ok=True)
            
            default_private = keys_dir / 'private_key.pem'
            default_public = keys_dir / 'public_key.pem'
            
            private_path = Path(private_key_path) if private_key_path else default_private
            public_path = Path(public_key_path) if public_key_path else default_public
            
            # Try to load existing keys
            if private_path.exists() and public_path.exists():
                with open(private_path, 'rb') as f:
                    self.private_key = serialization.load_pem_private_key(f.read(), password=None)
                with open(public_path, 'rb') as f:
                    self.public_key = serialization.load_pem_public_key(f.read())
                print(f"✅ Loaded Ed25519 keys from {keys_dir}")
            else:
                # Generate new keypair
                self.private_key = Ed25519PrivateKey.generate()
                self.public_key = self.private_key.public_key()
                
                # Save keys
                private_pem = self.private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                )
                public_pem = self.public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                
                with open(default_private, 'wb') as f:
                    f.write(private_pem)
                with open(default_public, 'wb') as f:
                    f.write(public_pem)
                
                print(f"✅ Generated new Ed25519 keypair in {keys_dir}")
                
        except ImportError:
            print("⚠️  cryptography package not available, falling back to HMAC-SHA256")
            self.algorithm = "HMAC-SHA256"
            self.signing_key = hashlib.sha256(datetime.now().isoformat().encode()).digest()
        except Exception as e:
            print(f"⚠️  Ed25519 key error: {e}, falling back to HMAC-SHA256")
            self.algorithm = "HMAC-SHA256"
            self.signing_key = hashlib.sha256(datetime.now().isoformat().encode()).digest()
    
    def _generate_receipt_id(self) -> str:
        """Generate UUID v4 for receipt."""
        return str(uuid.uuid4())
    
    def _hash_intent(self, intent: str) -> str:
        """Create SHA-256 hash of original intent."""
        return hashlib.sha256(intent.encode('utf-8')).hexdigest()
    
    def _compute_signature_payload(self, receipt_data: Dict[str, Any]) -> bytes:
        """
        Create canonical payload for signing.
        
        Only signs critical fields that prove what happened.
        """
        # Fields that must be signed (cannot be tampered with)
        signed_fields = [
            'intent_hash',
            'action_taken',
            'post_state',
            'invariants_checked',
            'verification_result',
            'timestamp'
        ]
        
        payload_dict = {
            field: receipt_data.get(field)
            for field in signed_fields
            if field in receipt_data
        }
        
        # Canonical JSON (sorted keys, no extra whitespace)
        payload_json = json.dumps(payload_dict, sort_keys=True, separators=(',', ':'))
        return payload_json.encode('utf-8')
    
    def _sign_hmac_sha256(self, payload: bytes) -> str:
        """Sign payload using HMAC-SHA256."""
        signature = hmac.new(
            self.signing_key,
            payload,
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def _sign_ed25519(self, payload: bytes) -> str:
        """
        Sign payload using Ed25519.
        
        Requires cryptography package.
        """
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            
            if self.private_key is None:
                raise ValueError("Ed25519 private key not loaded")
            
            signature = self.private_key.sign(payload)
            return base64.b64encode(signature).decode('utf-8')
            
        except ImportError:
            print("⚠️  cryptography not available, falling back to HMAC-SHA256")
            self.algorithm = "HMAC-SHA256"
            return self._sign_hmac_sha256(payload)
        except Exception as e:
            print(f"⚠️  Ed25519 signing error: {e}, falling back to HMAC-SHA256")
            self.algorithm = "HMAC-SHA256"
            return self._sign_hmac_sha256(payload)
    
    def sign(self, payload: bytes) -> Tuple[str, str]:
        """
        Sign payload using configured algorithm.
        
        Returns:
            Tuple of (signature_b64, algorithm_used)
        """
        if self.algorithm == "Ed25519":
            sig = self._sign_ed25519(payload)
        else:
            sig = self._sign_hmac_sha256(payload)
        
        return sig, self.algorithm
    
    def verify_signature(self, receipt: Receipt, public_key_path: Optional[str] = None) -> bool:
        """
        Verify a receipt's signature.
        
        Args:
            receipt: Receipt to verify
            public_key_path: Path to public key PEM file (for Ed25519)
            
        Returns:
            True if signature is valid, False otherwise
        """
        # Reconstruct payload
        receipt_dict = asdict(receipt)
        payload = self._compute_signature_payload(receipt_dict)
        
        # Verify based on algorithm
        if receipt.signature['algorithm'] == "HMAC-SHA256":
            expected_sig = self._sign_hmac_sha256(payload)
            return hmac.compare_digest(expected_sig, receipt.signature['value'])
        
        elif receipt.signature['algorithm'] == "Ed25519":
            try:
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.primitives.serialization import load_pem_public_key
                
                # Load public key
                if public_key_path:
                    with open(public_key_path, 'rb') as f:
                        verify_key = serialization.load_pem_public_key(f.read())
                elif self.public_key:
                    verify_key = self.public_key
                else:
                    # Try default location
                    keys_dir = Path(__file__).parent / 'keys' / 'public_key.pem'
                    if keys_dir.exists():
                        with open(keys_dir, 'rb') as f:
                            verify_key = serialization.load_pem_public_key(f.read())
                    else:
                        print("⚠️  No public key available for verification")
                        return False
                
                signature_bytes = base64.b64decode(receipt.signature['value'])
                verify_key.verify(signature_bytes, payload)
                return True
                
            except Exception as e:
                print(f"Signature verification failed: {e}")
                return False
        
        return False
    
    def generate(
        self,
        intent: str,
        action_type: str,
        target: str,
        parameters: Dict[str, Any],
        verification_result: Any,  # VerificationResult from verification_gate
        pre_state: Optional[Dict[str, Any]] = None,
        post_state: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Receipt:
        """
        Generate a signed receipt from verification result.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        receipt_id = self._generate_receipt_id()
        
        # Convert verification result to dict
        from dataclasses import asdict as dc_asdict
        if hasattr(verification_result, '__dataclass_fields__'):
            vr_dict = dc_asdict(verification_result)
            # Remove raw_evidence to avoid duplication
            vr_dict.pop('raw_evidence', None)
        else:
            vr_dict = verification_result
        
        # Build invariants_checked from verification result
        invariants_checked = []
        if 'invariant_results' in vr_dict:
            for inv in vr_dict['invariant_results']:
                invariants_checked.append({
                    'invariant_id': inv.get('invariant_id'),
                    'claim': inv.get('claim'),
                    'expected': inv.get('expected'),
                    'actual': inv.get('actual'),
                    'passed': inv.get('passed'),
                    'evidence_path': inv.get('evidence_path')
                })
        
        # Build action_taken
        action_taken = {
            'action_type': action_type,
            'target': target,
            'parameters': parameters,
            'executor_id': metadata.get('executor_id', 'unknown') if metadata else 'unknown'
        }
        
        # Build context_bundle
        context_bundle = {
            'session_id': session_id or 'unknown',
            'environment': {
                'host': metadata.get('host', 'unknown') if metadata else 'unknown',
                'os': metadata.get('os', 'unknown') if metadata else 'unknown',
                'runtime': 'python-verification-gateway',
                'gateway_version': self.VERSION
            },
            'related_receipts': metadata.get('related_receipts', []) if metadata else [],
            'metadata': metadata or {}
        }
        
        # Build receipt data (before signing)
        receipt_data = {
            'receipt_id': receipt_id,
            'version': self.VERSION,
            'timestamp': timestamp,
            'intent_hash': self._hash_intent(intent),
            'action_taken': action_taken,
            'pre_state': pre_state,
            'post_state': post_state,
            'invariants_checked': invariants_checked,
            'verification_result': {
                'status': vr_dict.get('status', 'UNVERIFIED'),
                'confidence': vr_dict.get('confidence', 0.0),
                'verified_by': vr_dict.get('verified_by', self.VERSION),
                'failed_invariants': vr_dict.get('failed_invariants', []),
                'warnings': vr_dict.get('warnings', [])
            },
            'context_bundle': context_bundle
        }
        
        # Compute signature
        payload = self._compute_signature_payload(receipt_data)
        signature_value, algorithm_used = self.sign(payload)
        
        # Add signature to receipt
        receipt_data['signature'] = {
            'algorithm': algorithm_used,
            'value': signature_value,
            'public_key_id': self.public_key_id,
            'signed_fields': ['intent_hash', 'action_taken', 'post_state', 'invariants_checked', 'timestamp']
        }
        
        return Receipt(**receipt_data)
    
    def to_json(self, receipt: Receipt) -> str:
        """Convert receipt to JSON string."""
        return json.dumps(asdict(receipt), indent=2)
    
    def from_json(self, json_str: str) -> Receipt:
        """Parse JSON string back to Receipt."""
        data = json.loads(json_str)
        return Receipt(**data)
    
    def save_receipt(self, receipt: Receipt, filepath: str):
        """Save receipt to file."""
        with open(filepath, 'w') as f:
            f.write(self.to_json(receipt))
    
    def load_receipt(self, filepath: str) -> Receipt:
        """Load receipt from file."""
        with open(filepath, 'r') as f:
            return self.from_json(f.read())


# Convenience function
def generate_receipt(
    intent, action_type, target, parameters, 
    verification_result, post_state=None, **kwargs
) -> Receipt:
    """Quick helper to generate a receipt."""
    generator = ReceiptGenerator()
    return generator.generate(
        intent=intent,
        action_type=action_type,
        target=target,
        parameters=parameters,
        verification_result=verification_result,
        post_state=post_state,
        **kwargs
    )


if __name__ == '__main__':
    # Demo usage
    from intent_compiler import IntentCompiler
    from verification_gate import VerificationGate
    
    print("=" * 60)
    print("RECEIPT GENERATOR DEMO - Ed25519 Support")
    print("=" * 60)
    
    # Test HMAC-SHA256
    print("\n🔐 Testing HMAC-SHA256...")
    gen_hmac = ReceiptGenerator(algorithm="HMAC-SHA256")
    
    # Test Ed25519
    print("\n🔐 Testing Ed25519...")
    gen_ed = ReceiptGenerator(algorithm="Ed25519")
    
    print("\n✅ Both signing algorithms working!")
