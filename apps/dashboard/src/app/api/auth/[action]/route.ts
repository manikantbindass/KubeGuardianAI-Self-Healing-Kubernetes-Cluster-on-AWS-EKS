import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import { NextResponse, type NextRequest } from "next/server";
import {
  accessCookie,
  appOrigin,
  cookieOptions,
  discovery,
  flowCookie,
  sameOrigin,
  seal,
  unseal,
  verifyIDToken,
} from "@/lib/server-auth";
export const dynamic = "force-dynamic";
type Context = { params: Promise<{ action: string }> };
async function backendSession(token: string) {
  return fetch(
    new URL(
      "/api/v1/ops/session",
      process.env.API_BASE_URL ?? "http://127.0.0.1:8000",
    ),
    {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    },
  );
}
export async function GET(request: NextRequest, context: Context) {
  const { action } = await context.params;
  if (action === "config")
    return NextResponse.json(
      {
        mode: process.env.OPS_AUTH_MODE ?? "oidc",
        oidc_configured: !!(
          process.env.OIDC_ISSUER && process.env.OIDC_CLIENT_ID
        ),
      },
      { headers: { "Cache-Control": "no-store" } },
    );
  try {
    if (action === "login") {
      const metadata = await discovery();
      const state = randomBytes(24).toString("base64url"),
        nonce = randomBytes(24).toString("base64url"),
        verifier = randomBytes(32).toString("base64url");
      const redirect = `${appOrigin(request)}/api/auth/callback`;
      const url = new URL(metadata.authorization_endpoint);
      const client = process.env.OIDC_CLIENT_ID;
      if (!client) throw new Error("Client ID missing");
      url.search = new URLSearchParams({
        client_id: client,
        response_type: "code",
        scope: "openid profile",
        redirect_uri: redirect,
        state,
        nonce,
        code_challenge: createHash("sha256")
          .update(verifier)
          .digest("base64url"),
        code_challenge_method: "S256",
      }).toString();
      const response = NextResponse.redirect(url);
      response.cookies.set(
        flowCookie,
        seal({ state, nonce, verifier, redirect, issued: Date.now() }),
        { ...cookieOptions(), maxAge: 600 },
      );
      return response;
    }
    if (action === "callback") {
      const flow = unseal<{
        state: string;
        nonce: string;
        verifier: string;
        redirect: string;
        issued: number;
      }>(request.cookies.get(flowCookie)?.value ?? "");
      const state = request.nextUrl.searchParams.get("state") ?? "";
      const code = request.nextUrl.searchParams.get("code");
      if (
        !code ||
        state.length !== flow.state.length ||
        !timingSafeEqual(Buffer.from(state), Buffer.from(flow.state)) ||
        Date.now() - flow.issued > 600000
      )
        throw new Error("Expired or invalid OIDC state");
      const metadata = await discovery();
      const client = process.env.OIDC_CLIENT_ID!;
      const values = new URLSearchParams({
        grant_type: "authorization_code",
        code,
        client_id: client,
        redirect_uri: flow.redirect,
        code_verifier: flow.verifier,
      });
      const headers: Record<string, string> = {
        "Content-Type": "application/x-www-form-urlencoded",
      };
      if (process.env.OIDC_CLIENT_SECRET)
        headers.Authorization = `Basic ${Buffer.from(`${encodeURIComponent(client)}:${encodeURIComponent(process.env.OIDC_CLIENT_SECRET)}`).toString("base64")}`;
      const exchange = await fetch(metadata.token_endpoint, {
        method: "POST",
        body: values,
        headers,
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
      });
      const tokens = (await exchange.json()) as {
        access_token?: string;
        id_token?: string;
        expires_in?: number;
      };
      if (
        !exchange.ok ||
        !tokens.access_token ||
        !tokens.id_token ||
        tokens.access_token.length > 3800
      )
        throw new Error("OIDC exchange failed");
      await verifyIDToken(
        tokens.id_token,
        metadata.issuer,
        client,
        metadata.jwks_uri,
        flow.nonce,
      );
      if (!(await backendSession(tokens.access_token)).ok)
        throw new Error("API audience or role validation failed");
      const response = NextResponse.redirect(new URL("/", appOrigin(request)));
      response.cookies.set(accessCookie, tokens.access_token, {
        ...cookieOptions(),
        maxAge: Math.min(tokens.expires_in ?? 600, 3600),
      });
      response.cookies.delete(flowCookie);
      return response;
    }
  } catch {
    const response = NextResponse.json(
      {
        error:
          "Sign-in failed. Check issuer, audience, client settings and callback URL.",
      },
      { status: 401 },
    );
    response.cookies.delete(flowCookie);
    return response;
  }
  return NextResponse.json({ error: "Unknown auth route" }, { status: 404 });
}
export async function POST(request: NextRequest, context: Context) {
  if (!sameOrigin(request))
    return NextResponse.json(
      { error: "Same-origin request required" },
      { status: 403 },
    );
  const { action } = await context.params;
  if (action === "logout") {
    const response = NextResponse.json({ status: "signed_out" });
    response.cookies.delete(accessCookie);
    response.cookies.delete(flowCookie);
    return response;
  }
  if (action !== "development" || process.env.OPS_AUTH_MODE !== "development")
    return NextResponse.json(
      { error: "Local authentication is not enabled" },
      { status: 404 },
    );
  try {
    const body = await request.text();
    if (body.length > 1024)
      return NextResponse.json({ error: "Invalid token" }, { status: 400 });
    const { token } = JSON.parse(body) as { token: string };
    if (
      typeof token !== "string" ||
      token.length > 512 ||
      !(await backendSession(token)).ok
    )
      return NextResponse.json(
        { error: "Token not accepted" },
        { status: 401 },
      );
    const response = NextResponse.json({ status: "authenticated" });
    response.cookies.set(accessCookie, token, {
      ...cookieOptions(),
      maxAge: 3600,
    });
    return response;
  } catch {
    return NextResponse.json(
      { error: "Authentication service unavailable" },
      { status: 503 },
    );
  }
}
