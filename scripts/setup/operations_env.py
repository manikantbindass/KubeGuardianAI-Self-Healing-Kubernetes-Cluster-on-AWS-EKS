"""Generate ignored local ops credentials without printing secret values or overwriting settings."""

import argparse
import base64
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--development", action="store_true", help="explicitly enable trusted-local authentication"
    )
    parser.add_argument(
        "--demo", action="store_true", help="explicitly make synthetic demo mode available"
    )
    args = parser.parse_args()
    directory = ROOT / ".cache/operations"
    directory.mkdir(parents=True, exist_ok=True)
    key_path = directory / "approver.key"
    if not key_path.exists():
        key = Ed25519PrivateKey.generate()
        private = key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        public = key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as file:
            file.write(base64.b64encode(private + public).decode())
        (directory / "public-key.txt").write_text(
            base64.b64encode(public).decode(), encoding="utf-8"
        )
    path = ROOT / ".env"
    body = (
        path.read_text(encoding="utf-8")
        if path.exists()
        else (ROOT / ".env.example").read_text(encoding="utf-8")
    )
    current = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in body.splitlines()
        if "=" in line and not line.startswith("#")
    }
    if args.development:
        if current.get("APP_ENV", "local") != "local" or current.get("OIDC_ISSUER"):
            raise SystemExit("Refusing to replace configured nonlocal/OIDC authentication")
        body = (
            "\n".join(line for line in body.splitlines() if not line.startswith("OPS_AUTH_MODE="))
            + "\n"
        )
        current.pop("OPS_AUTH_MODE", None)
    if args.demo:
        body = (
            "\n".join(
                line for line in body.splitlines() if not line.startswith("OPS_DEMO_ENABLED=")
            )
            + "\n"
        )
        current.pop("OPS_DEMO_ENABLED", None)
    if os.name != "nt" and int(getattr(os, "getuid", lambda: 10001)()):
        # The local override runs the API as the unprivileged signing-key owner.
        for name in ("OPS_RUNTIME_UID", "OPS_RUNTIME_GID"):
            body = (
                "\n".join(line for line in body.splitlines() if not line.startswith(name + "="))
                + "\n"
            )
            current.pop(name, None)
    defaults = {
        "OPS_AUTH_MODE": "development" if args.development else "oidc",
        "OPS_DEV_TOKEN": secrets.token_urlsafe(32),
        "OPS_DEV_VIEWER_TOKEN": secrets.token_urlsafe(32),
        "OPS_BRIDGE_TOKEN": secrets.token_urlsafe(32),
        "AUTH_SESSION_SECRET": secrets.token_urlsafe(32),
        "OPS_DEMO_ENABLED": "true" if args.demo else "false",
        "OPS_APPROVAL_KEY_PATH": ".cache/operations/approver.key",
        "OPS_APPROVAL_KEY_ID": "dashboard-approver",
        "OPS_RUNTIME_UID": str(int(getattr(os, "getuid", lambda: 10001)()))
        if os.name != "nt" and int(getattr(os, "getuid", lambda: 10001)())
        else "10001",
        "OPS_RUNTIME_GID": str(int(getattr(os, "getgid", lambda: 10001)()))
        if os.name != "nt" and int(getattr(os, "getgid", lambda: 10001)())
        else "10001",
        "APP_PUBLIC_URL": "http://localhost:3000",
    }
    for name, value in defaults.items():
        if not current.get(name):
            lines = body.splitlines()
            found = False
            for index, line in enumerate(lines):
                if line.startswith(name + "="):
                    lines[index], found = f"{name}={value}", True
            if not found:
                lines.append(f"{name}={value}")
            body = "\n".join(lines) + "\n"
    path.write_text(body, encoding="utf-8")
    print("Local configuration saved to ignored .env; signing key is in .cache/operations.")
    print("Use OPS_DEV_TOKEN locally; never paste it into issues, logs or screenshots.")
    print(
        "The generated public key must be explicitly trusted by the operator "
        "before approval delivery."
    )


if __name__ == "__main__":
    main()
