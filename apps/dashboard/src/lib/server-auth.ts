import {
  createCipheriv,
  createDecipheriv,
  createHash,
  randomBytes,
} from "node:crypto";
import { createRemoteJWKSet, jwtVerify } from "jose";
import type { NextRequest } from "next/server";
export const accessCookie = "sentinel_access";
export const flowCookie = "sentinel_oidc_flow";
export function appOrigin(request: Request) {
  return new URL(process.env.APP_PUBLIC_URL ?? request.url).origin;
}
export function sameOrigin(request: Request) {
  return request.headers.get("origin") === appOrigin(request);
}
export function cookieOptions() {
  return {
    httpOnly: true,
    secure:
      process.env.APP_COOKIE_SECURE === "true" ||
      !!process.env.APP_PUBLIC_URL?.startsWith("https://"),
    sameSite: "lax" as const,
    path: "/",
  };
}
function secret() {
  const value = process.env.AUTH_SESSION_SECRET;
  if (!value || value.length < 32)
    throw new Error(
      "AUTH_SESSION_SECRET must contain at least 32 random characters",
    );
  return createHash("sha256").update(value).digest();
}
export function seal(value: unknown) {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", secret(), iv);
  const ciphertext = Buffer.concat([
    cipher.update(JSON.stringify(value)),
    cipher.final(),
  ]);
  return Buffer.concat([iv, cipher.getAuthTag(), ciphertext]).toString(
    "base64url",
  );
}
export function unseal<T>(value: string): T {
  const body = Buffer.from(value, "base64url");
  const decipher = createDecipheriv(
    "aes-256-gcm",
    secret(),
    body.subarray(0, 12),
  );
  decipher.setAuthTag(body.subarray(12, 28));
  return JSON.parse(
    Buffer.concat([
      decipher.update(body.subarray(28)),
      decipher.final(),
    ]).toString(),
  ) as T;
}
export function sessionToken(request: NextRequest) {
  return request.cookies?.get(accessCookie)?.value;
}
export async function discovery() {
  const issuer = process.env.OIDC_ISSUER;
  if (
    !issuer ||
    (!issuer.startsWith("https://") &&
      process.env.OIDC_ALLOW_HTTP_LOCAL !== "true")
  )
    throw new Error("Secure OIDC issuer is not configured");
  const response = await fetch(
    `${issuer.replace(/\/$/, "")}/.well-known/openid-configuration`,
    { signal: AbortSignal.timeout(4000), cache: "no-store" },
  );
  if (!response.ok) throw new Error("OIDC discovery unavailable");
  const body = (await response.json()) as {
    issuer: string;
    authorization_endpoint: string;
    token_endpoint: string;
    jwks_uri: string;
  };
  if (body.issuer !== issuer) throw new Error("OIDC issuer mismatch");
  for (const endpoint of [
    body.authorization_endpoint,
    body.token_endpoint,
    body.jwks_uri,
  ]) {
    const url = new URL(endpoint);
    if (
      url.protocol !== "https:" &&
      process.env.OIDC_ALLOW_HTTP_LOCAL !== "true"
    )
      throw new Error("Insecure OIDC endpoint");
  }
  return body;
}
export async function verifyIDToken(
  token: string,
  issuer: string,
  audience: string,
  jwks: string,
  nonce: string,
) {
  const result = await jwtVerify(
    token,
    createRemoteJWKSet(new URL(jwks), { timeoutDuration: 4000 }),
    {
      issuer,
      audience,
      algorithms: ["RS256"],
      requiredClaims: ["exp", "iat", "sub", "nonce"],
    },
  );
  if (result.payload.nonce !== nonce) throw new Error("OIDC nonce mismatch");
  return result.payload;
}
