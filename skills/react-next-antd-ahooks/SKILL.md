---
name: react-next-antd-ahooks
description: Build, refactor, review, or optimize React and Next.js frontends that should use Ant Design and prefer ahooks for stateful client logic. Use when requests mention React, Next.js, App Router, Ant Design, antd, ahooks, dashboard or admin UI, CRUD pages, tables, forms, search and filter flows, modal workflows, or frontend coding standards.
---

# React Next Antd Ahooks

Build product-facing or admin-facing UIs with a TypeScript-first React and Next.js workflow. Default to Ant Design for business UI primitives and prefer ahooks when it removes manual hook boilerplate.

## Start

1. Detect whether the task is:
   - a pure React SPA
   - a Next.js App Router application
   - an existing mixed codebase with established patterns that must be preserved
2. Preserve the existing architecture unless it is clearly broken. Introduce this skill's defaults only where they improve the code without fighting the repo.
3. Read the minimum reference files needed:
   - Read [references/react.md](references/react.md) when editing component logic, state flow, effects, or composition.
   - Read [references/nextjs.md](references/nextjs.md) when editing routing, layout, data fetching, server/client boundaries, or deployment-sensitive behavior.
   - Read [references/antd-ahooks.md](references/antd-ahooks.md) when building forms, tables, filters, drawers, modals, async flows, or reusable stateful UI helpers.

## Default Stack

- Use TypeScript, function components, and named exports unless the repo already standardizes differently.
- Use Next.js App Router by default for new Next work.
- Use Server Components by default in Next.js. Add `'use client'` only around interactive islands.
- Use Ant Design as the first-choice component library for business UI.
- Use ahooks as the first-choice utility hook library when it replaces repetitive state, async, debounce, pagination, storage, or toggle logic.

## Working Rules

1. Shape the page around user tasks, not around component demos.
2. Keep pages thin and move domain behavior into feature components, hooks, and service helpers.
3. Keep a single `.tsx` file under roughly 500 lines whenever practical. If a page or component approaches that size, split it before adding more logic.
4. Split large screens by responsibility: page shell, filter area, table area, modal or drawer flows, form sections, and shared view models should not stay in one monolithic file.
5. Prefer internal feature components first. Promote a component to a global shared component only after real cross-feature reuse appears.
6. Keep derived values in render. Do not mirror props or computed values into state without a clear external-sync requirement.
7. Use effects only to synchronize with external systems. Do not use effects for logic that belongs in render, event handlers, or server data loading.
8. Prefer ahooks over custom ad hoc hooks when an official ahooks primitive already fits the problem.
9. Keep Ant Design usage idiomatic. Prefer tokens, built-in layout primitives, and official patterns before custom CSS or bespoke widgets.
10. Deliver complete UX states: loading, empty, error, disabled, and success feedback.

## ahooks Preference Rule

Prefer ahooks when it removes manual lifecycle wiring or repeated local utilities:

- Use `useRequest` for client-side async requests, polling, refresh, manual triggers, pagination adapters, and request status management.
- Use `useBoolean` or `useToggle` for modal, drawer, popover, and feature-flag state.
- Use `useSetState` for compact object state in filter panels and forms adjacent to Ant Design components.
- Use `useDebounceFn`, `useThrottleFn`, or `useDebounce` for search inputs and resize-driven updates.
- Use `useLocalStorageState` or `useSessionStorageState` for persisted UI preferences.
- Use `usePagination`, `useInfiniteScroll`, `useSelections`, `useControllableValue`, or other domain-fit hooks instead of rebuilding them.

Keep native React hooks for the fundamentals:

- Use `useState` for trivial one-value local state.
- Use `useRef` for instance storage or DOM access.
- Use `useEffect`, `useLayoutEffect`, or `useEffectEvent` only when integrating with external systems or subscriptions.

## Delivery Checklist

Before finishing, verify that the result:

1. respects server/client boundaries in Next.js
2. keeps each `.tsx` file at a manageable size and avoids page-sized monoliths
3. splits large UI into internal feature components before introducing global abstractions
4. avoids unnecessary custom hooks or effect chains
5. uses Ant Design components and tokens consistently
6. chooses ahooks where they simplify code materially
7. keeps types explicit at module boundaries
8. includes accessible labels and keyboard-safe interactions
9. matches existing repo conventions where those conventions are deliberate

## References

- Use [references/react.md](references/react.md) for component design, state, effects, and hook discipline.
- Use [references/nextjs.md](references/nextjs.md) for App Router, rendering strategy, caching, routing, and project structure.
- Use [references/antd-ahooks.md](references/antd-ahooks.md) for Ant Design usage, theming, forms/tables, and ahooks mapping.
