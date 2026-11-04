"""Regression boundaries for the local Checkov verification dependency replacement."""

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

from checkov.common.external_checks.verification.errors import SignatureVerificationError
from checkov.common.external_checks.verification.keys import load_public_keys
from checkov.common.external_checks.verification.verifier import (
    VerificationResult,
    _signature_is_well_formed,
    verify_bytes,
    verify_file,
)
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa, utils


class CryptoBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "public.pem"
        self.private = ec.generate_private_key(ec.SECP256R1())
        self.write_public(self.private.public_key())
        self.keys = load_public_keys([str(self.path)])
        self.payload = b"# signed external policy\nallow = False\n"
        self.signature = self.private.sign(self.payload, ec.ECDSA(hashes.SHA256()))
        self.signed = self.payload + b"# checkov-digest: " + self.signature.hex().encode() + b"\n"

    def write_public(self, key: ec.EllipticCurvePublicKey | rsa.RSAPublicKey) -> None:
        self.path.write_bytes(
            key.public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )

    def test_valid_signature_and_standard_spki_fingerprint(self) -> None:
        self.assertEqual(
            verify_bytes(self.signed, self.keys), (VerificationResult.OK, self.payload)
        )
        der = self.private.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self.assertEqual(self.keys[0].fingerprint_hex, hashlib.sha256(der).hexdigest())
        self.assertIsNone(importlib.util.find_spec("ecdsa"))

    def test_modified_payload_wrong_key_and_missing_signature_fail_closed(self) -> None:
        self.assertNotEqual(
            verify_bytes(self.signed.replace(b"False", b"True"), self.keys)[0],
            VerificationResult.OK,
        )
        self.write_public(ec.generate_private_key(ec.SECP256R1()).public_key())
        result, payload = verify_bytes(self.signed, load_public_keys([str(self.path)]))
        self.assertEqual(result, VerificationResult.UNKNOWN_KEY)
        self.assertEqual(payload, b"")
        self.assertEqual(
            verify_bytes(self.payload, self.keys), (VerificationResult.NO_SIGNATURE, b"")
        )
        with self.assertRaises(ValueError):
            verify_bytes(self.signed, [])

    def test_rejects_other_curves_rsa_private_keys_and_malformed_pem(self) -> None:
        for key in (
            ec.generate_private_key(ec.SECP384R1()).public_key(),
            rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key(),
        ):
            self.write_public(key)
            with self.assertRaises(SignatureVerificationError):
                load_public_keys([str(self.path)])
        for raw in (
            b"not a key",
            self.private.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        ):
            self.path.write_bytes(raw)
            with self.assertRaises(SignatureVerificationError):
                load_public_keys([str(self.path)])

    def test_malformed_der_out_of_range_double_trailer_and_io_error(self) -> None:
        for raw in (
            b"invalid DER",
            utils.encode_dss_signature(0, 1),
            utils.encode_dss_signature(1, 2**256),
        ):
            self.assertFalse(_signature_is_well_formed(raw))
        doubled = self.signed + b"# checkov-digest: " + self.signature.hex().encode() + b"\n"
        self.assertEqual(verify_bytes(doubled, self.keys), (VerificationResult.DOUBLE_TRAILER, b""))
        malformed = self.payload + b"# checkov-digest: " + b"00" * 65 + b"\n"
        self.assertEqual(
            verify_bytes(malformed, self.keys), (VerificationResult.BAD_SIGNATURE, b"")
        )
        self.assertEqual(
            verify_file(str(self.path.parent / "missing"), self.keys),
            (VerificationResult.IO_ERROR, b""),
        )


if __name__ == "__main__":
    unittest.main()
