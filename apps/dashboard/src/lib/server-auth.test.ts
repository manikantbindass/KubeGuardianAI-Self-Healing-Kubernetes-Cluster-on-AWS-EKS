import { afterEach, describe, expect, it, vi } from "vitest";
import { seal, unseal, sameOrigin, cookieOptions } from "./server-auth";
afterEach(() => vi.unstubAllEnvs());
describe("server authentication", () => {
  it("encrypts and authenticates PKCE state without plaintext secrets", () => {
    vi.stubEnv("AUTH_SESSION_SECRET", "a".repeat(40));
    const value = {
      state: "state",
      verifier: "private-verifier",
      nonce: "nonce",
    };
    const sealed = seal(value);
    expect(sealed).not.toContain("private-verifier");
    expect(unseal(sealed)).toEqual(value);
    const bytes = Buffer.from(sealed, "base64url");
    bytes[30] ^= 1;
    expect(() => unseal(bytes.toString("base64url"))).toThrow();
  });
  it("fails closed without an adequate session secret", () => {
    vi.stubEnv("AUTH_SESSION_SECRET", "short");
    expect(() => seal({})).toThrow();
  });
  it("rejects cross-origin mutations and uses secure HttpOnly cookies over TLS", () => {
    vi.stubEnv("APP_PUBLIC_URL", "https://sentinel.example");
    expect(
      sameOrigin(
        new Request("https://internal/api", {
          headers: { Origin: "https://attacker.example" },
        }),
      ),
    ).toBe(false);
    expect(
      sameOrigin(
        new Request("https://internal/api", {
          headers: { Origin: "https://sentinel.example" },
        }),
      ),
    ).toBe(true);
    expect(cookieOptions()).toMatchObject({
      httpOnly: true,
      secure: true,
      sameSite: "lax",
    });
  });
});
