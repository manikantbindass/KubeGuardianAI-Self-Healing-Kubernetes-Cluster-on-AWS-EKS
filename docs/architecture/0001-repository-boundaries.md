# ADR 0001: Repository and application boundaries

Status: Accepted design | Date: 2026-11-02

## Context

The initial repository contains only LICENSE. Future frontend, Python analysis, operator, and infrastructure need coordinated contracts without implying that directory creation implements them.

## Decision

Use a monorepo with responsibility notes under apps, services, operator, ml, infrastructure, docs, scripts, tests, and .github. Plan Next.js/TypeScript/Tailwind for the frontend, FastAPI for the backend, and a Go operator at the execution boundary. Begin backend domain components in a modular process and split only when measured scale, ownership, or isolation requires it. Preserve LICENSE and Git ancestry; recommend a separately authorized rename.

Documentation tooling is pinned and locked in Phase 00. Add exact application packages and lockfiles with the Phase 01 vertical slice. Node 24 and Python 3.12 are the planned starting toolchains, subject to compatibility validation.

## Alternatives and consequences

Polyrepos allow independent lifecycles but complicate atomic contract changes. A fully distributed microservice deployment adds operational cost before load is known. This monorepo permits shared reviews and gradual extraction; directories do not mandate separate deployments. Go adds a future toolchain but keeps operator privilege separate from Python inference and API concerns. See the [system overview](system-overview.md) for alternatives and interfaces.
