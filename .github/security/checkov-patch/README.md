# Checkov cryptography dependency replacement

This is an explicit downstream build, `3.4.3+sentinel.1`, not an upstream security
release. Checkov 3.4.3 uses python-ecdsa only for its external-policy P-256/SHA-256
signature verification. The dependency also exposes vulnerable signing/key
generation code (CVE-2024-23342) with no upstream fix. This build removes that
dependency entirely and uses OpenSSL-backed `cryptography==50.0.2` for public-key
loading, DER signature decoding and signature verification. It retains the same
curve/hash restriction, SPKI fingerprint, trailer format and failure results.
All Terraform checks and severity gates remain unchanged. No advisory is ignored.

`build.py` downloads the exact upstream PyPI wheel and checks its committed
SHA-256 before changing two source modules, the explicit local version and
dependency metadata. It rejects ambiguous patches and any remaining python-ecdsa
imports. It rebuilds wheel RECORD hashes with deterministic archive metadata.
The upstream license is retained in the wheel. The generated wheel is committed
under `../vendor` and selected through the frozen security lock.

Reproduce from the repository root:

```sh
python .github/security/checkov-patch/build.py
uv sync --project .github/security --frozen
uv run --project .github/security python .github/security/checkov-patch/test_crypto.py
```

The standard-library test runner verifies valid signatures and fingerprint
compatibility, rejects changed payloads/wrong keys/other curves/RSA/private keys,
malformed DER/out-of-range signature integers, duplicate trailers, missing files,
and empty trust sets. It also asserts python-ecdsa is absent. CI executes these
tests before the actual Terraform scan. Return to upstream once its dependency
is safely replaced; never strip a dependency from metadata without replacing
and testing the consuming implementation.
