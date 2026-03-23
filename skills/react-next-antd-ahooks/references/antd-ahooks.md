# Ant Design And ahooks Rules

Use this reference when building business UI, especially admin panels, data tables, search forms, drawers, and modal workflows.

## Ant Design Defaults

- Prefer Ant Design primitives before building custom atoms for common business UI.
- Use `App`, `ConfigProvider`, and theme tokens as the primary composition points.
- Prefer token-based theming over scattered CSS overrides.
- Reuse Ant Design spacing, typography, grid, and feedback components for visual consistency.

## Forms

- Let Ant Design `Form` own field state unless there is a strong cross-form requirement.
- Avoid mirroring every field into React state.
- Use form validation rules, `Form.Item`, and built-in status feedback before writing custom validation plumbing.
- Use `dependencies` for cross-field reactions before reaching for broad `shouldUpdate` blocks.
- Submit through form semantics, not custom click chains.

## Tables And Search Panels

- Keep table queries, filters, pagination, and sorting in one coherent state model.
- Keep column definitions readable and move heavy cell logic into small render helpers or subcomponents.
- Pair tables with `useRequest` or `usePagination` instead of custom loading/error wiring.
- Consider `useAntdTable` when a client-heavy page needs tight Ant Design `Form` and `Table` binding and the repo is already comfortable with that pattern.
- Keep empty and error placeholders within the table region, not as afterthoughts.

## Feedback And Overlays

- Use Ant Design `message`, `notification`, `Modal`, `Drawer`, and `Popconfirm` deliberately.
- Keep destructive actions explicit and confirmable.
- Keep overlay state simple with `useBoolean` or `useToggle`.
- Prefer `Modal.useModal` or context-aware APIs when theming and app context must flow into overlays.

## ahooks Mapping

Choose the narrowest ahooks primitive that removes boilerplate cleanly.

- Async request lifecycle: `useRequest`
- Table pagination or list paging: `usePagination`
- Boolean visibility state: `useBoolean`, `useToggle`
- Search debounce: `useDebounceFn`, `useThrottleFn`
- Local object patch state: `useSetState`
- Persistent UI preferences: `useLocalStorageState`, `useSessionStorageState`
- Controlled/uncontrolled bridge components: `useControllableValue`
- Multi-select helpers: `useSelections`

## When Not To Force ahooks

- Do not wrap a single `open/close` state in a more complex abstraction if `useBoolean` gives no real gain over existing repo patterns.
- Do not use client-side ahooks to replace server-first Next.js data loading.
- Do not stack multiple ahooks where one simpler flow would be clearer.

## Source Notes

- Ant Design documentation recommends using `ConfigProvider` and design tokens for theme customization.
- Ant Design documentation documents a dedicated Next.js integration path for App Router SSR styles.
- ahooks documentation centers on reusable hooks such as `useRequest`, `useBoolean`, and `usePagination` to replace repetitive stateful patterns.
- Official references:
  - [Usage with Next.js](https://ant.design/docs/react/use-with-next/)
  - [Customize Theme](https://ant.design/docs/react/customize-theme/)
  - [Form](https://ant.design/components/form/)
  - [ahooks GitHub repository](https://github.com/alibaba/hooks)
