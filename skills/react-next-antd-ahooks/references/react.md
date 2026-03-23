# React Rules

Use this reference when editing component behavior, local state, effects, event flow, or reusable hooks.

## Component Design

- Keep components focused on one UI responsibility.
- Let page files compose sections; let feature components own domain behavior.
- Prefer composition over prop-heavy mega-components.
- Keep a single `.tsx` file under roughly 500 lines whenever practical. Treat that threshold as a refactor trigger, not a target to exceed casually.
- Split by responsibility before a file becomes dense: extract section components, modal or drawer components, table wrappers, form blocks, empty states, and domain hooks.
- Prefer internal components inside the feature directory for page-specific UI. Move a component to a shared global location only after repeated reuse is proven.
- If one file mixes page layout, table columns, modal flows, request wiring, and form schema, split those concerns into adjacent files.
- Keep module boundaries explicit: props, return types for exported helpers, and service contracts should stay typed.
- Avoid `any`. If a third-party type is poor, isolate the escape hatch near the boundary.

## State Rules

- Keep the smallest possible source of truth.
- Compute derived values during render instead of syncing them into state.
- Lift state only when multiple siblings truly need the same live source of truth.
- Keep transient UI state local to the nearest interactive component.
- Prefer reducers only when transitions are genuinely complex. Do not default to reducers for ordinary form or toggle state.

## Effect Discipline

Follow the React guidance that effects are for synchronizing with external systems, not for ordinary data flow or event logic.

- Do not fetch data in a client effect if the same data can be loaded on the server or higher in the tree.
- Do not use an effect to respond to a click, submit, or selection change when a direct event handler is clearer.
- Do not chain effects that only derive state from other state.
- Use cleanup consistently for subscriptions, timers, listeners, and imperative libraries.
- Use `useEffectEvent` when an effect-driven subscription needs the latest values without re-subscribing on every render.

## Memoization

- Assume modern React tooling can already optimize many cases.
- Add `useMemo` or `useCallback` only when there is a measured rendering issue, an unstable dependency boundary, or an API that requires stable identity.
- Prefer simpler code over speculative memoization.

## Reusable Logic

- Extract a custom hook only after the logic clearly repeats or materially improves readability.
- Check ahooks before writing a new utility hook from scratch.
- Keep custom hooks narrow and domain-oriented. A hook should expose a coherent behavior, not a bag of unrelated state.

## UI Quality

- Keep render paths deterministic and side-effect free.
- Handle loading, empty, error, and permission-limited states explicitly.
- Keep button labels action-oriented and form copy unambiguous.
- Preserve keyboard navigation and visible focus states.

## Source Notes

- React documentation emphasizes that many effects are unnecessary and should be replaced with render-time derivation or event handlers.
- React documentation also recommends extracting shared logic into custom hooks only when there is real reuse.
- Official references:
  - [You Might Not Need an Effect](https://react.dev/learn/you-might-not-need-an-effect)
  - [Reusing Logic with Custom Hooks](https://react.dev/learn/reusing-logic-with-custom-hooks)
  - [useEffectEvent](https://react.dev/reference/react/useEffectEvent)
  - [React Compiler introduction](https://react.dev/learn/react-compiler/introduction)
