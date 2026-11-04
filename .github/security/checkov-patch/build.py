"""Rebuild a pinned upstream Checkov wheel with OpenSSL-backed signature verification."""

import base64
import csv
import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = (
    "https://files.pythonhosted.org/packages/65/3a/"
    "089f27b8bbdd36692e3225b5fb5878728be4552cac198b0413c76dadf8a8/"
    "checkov-3.4.3-py3-none-any.whl"
)
SHA256 = "666f376019f6a9fdbeb5c9d2a57be3fb83a4acd2d924d447942450a926ba0f55"
VERSION = "3.4.3+sentinel.1"
PREFIX = "checkov/common/external_checks/verification/"


def replace_once(text: str, before: str, after: str) -> str:
    if text.count(before) != 1:
        raise ValueError("Upstream source changed; refusing ambiguous patch")
    return text.replace(before, after, 1)


def build() -> Path:
    with urllib.request.urlopen(UPSTREAM, timeout=60) as response:
        raw = response.read(10_000_000)
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError("Upstream wheel hash mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as wheel:
        files = {name: wheel.read(name) for name in wheel.namelist()}
    old_info = "checkov-3.4.3.dist-info/"
    new_info = f"checkov-{VERSION}.dist-info/"
    files = {
        name.replace(old_info, new_info).replace(
            "checkov-3.4.3.data/", f"checkov-{VERSION}.data/"
        ): body
        for name, body in files.items()
    }
    record = new_info + "RECORD"
    files.pop(record)
    metadata = files[new_info + "METADATA"].decode()
    metadata = replace_once(metadata, "Version: 3.4.3\n", f"Version: {VERSION}\n")
    requirements = [
        line for line in metadata.splitlines() if line.startswith("Requires-Dist: ecdsa")
    ]
    if len(requirements) != 1:
        raise ValueError("Expected exact upstream ecdsa dependency")
    metadata = replace_once(metadata, requirements[0], "Requires-Dist: cryptography==50.0.2")
    files[new_info + "METADATA"] = metadata.encode()
    keys = files[PREFIX + "keys.py"].decode()
    start = keys.index("# ecdsa ships")
    end = keys.index("from .errors")
    keys = (
        keys[:start]
        + (
            "from cryptography.exceptions import UnsupportedAlgorithm\n"
            "from cryptography.hazmat.primitives import serialization\n"
            "from cryptography.hazmat.primitives.asymmetric import ec\n\n"
        )
        + keys[end:]
    )
    keys = keys.replace("    UnexpectedDER,\n", "    UnsupportedAlgorithm,\n")
    keys = keys.replace("    MalformedPointError,\n", "")
    keys = keys.replace("VerifyingKey", "ec.EllipticCurvePublicKey")
    keys = replace_once(
        keys,
        "if vk.curve != NIST256p:",
        "if not isinstance(vk, ec.EllipticCurvePublicKey) "
        "or not isinstance(vk.curve, ec.SECP256R1):",
    )
    keys = replace_once(
        keys, "ec.EllipticCurvePublicKey.from_pem(pem)", "serialization.load_pem_public_key(pem)"
    )
    keys = replace_once(
        keys,
        "validated.to_der()",
        "validated.public_bytes(serialization.Encoding.DER, "
        "serialization.PublicFormat.SubjectPublicKeyInfo)",
    )
    files[PREFIX + "keys.py"] = keys.encode()
    verifier = files[PREFIX + "verifier.py"].decode()
    start = verifier.index("# ecdsa ships")
    end = verifier.index("from .keys")
    verifier = (
        verifier[:start]
        + (
            "from cryptography.exceptions import InvalidSignature\n"
            "from cryptography.hazmat.primitives import hashes\n"
            "from cryptography.hazmat.primitives.asymmetric import ec, utils\n\n"
        )
        + verifier[end:]
    )
    verifier = verifier.replace("import hashlib\n", "")
    verifier = replace_once(
        verifier,
        "_SECP256R1_N = NIST256p.order",
        "_SECP256R1_N = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551",
    )
    verifier = verifier.replace("    BadSignatureError,\n", "    InvalidSignature,\n")
    verifier = verifier.replace("    UnexpectedDER,\n", "").replace(
        "    MalformedPointError,\n", ""
    )
    verifier = replace_once(
        verifier, "sigdecode_der(sig_der, _SECP256R1_N)", "utils.decode_dss_signature(sig_der)"
    )
    verifier = replace_once(
        verifier,
        "sig_der, payload, hashfunc=hashlib.sha256, sigdecode=sigdecode_der,",
        "sig_der, payload, ec.ECDSA(hashes.SHA256()),",
    )
    files[PREFIX + "verifier.py"] = verifier.encode()
    # Any new upstream import would invalidate the complete dependency replacement.
    for name, body in files.items():
        if name.endswith(".py") and (b"from ecdsa" in body or b"import ecdsa" in body):
            raise ValueError(f"Unpatched dependency reference: {name}")
    rows = []
    for name, body in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(body).digest()).rstrip(b"=").decode()
        rows.append((name, "sha256=" + digest, str(len(body))))
    rows.append((record, "", ""))
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    files[record] = output.getvalue().encode()
    target = ROOT / "vendor" / f"checkov-{VERSION}-py3-none-any.whl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as wheel:
        for name, body in sorted(files.items()):
            entry = zipfile.ZipInfo(name, (2026, 11, 4, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (0o755 if ".data/scripts/" in name else 0o644) << 16
            wheel.writestr(entry, body)
    print(target.name, hashlib.sha256(target.read_bytes()).hexdigest())
    return target


if __name__ == "__main__":
    build()
