# Next.js Rules

Use this reference when working inside a Next.js application, especially App Router code.

## Rendering Strategy

- Default to App Router for new work.
- Default to Server Components. Move only interactive or browser-dependent sections behind `'use client'`.
- Keep client components small and leaf-oriented when possible.
- Pass only serializable data across the server/client boundary.

## Data Fetching

- Fetch data on the server whenever it does not require immediate client-only APIs.
- Use route `params`, `searchParams`, server actions, and server-side data loading as the first choice in App Router flows.
- Avoid duplicating the same fetch on both server and client unless there is a clear hydration or live-update need.
- Use client-side `useRequest` only for user-driven refresh, optimistic workflows, dashboards with live controls, or purely client-held state.

## Routing And URL State

- Model shareable page state in the URL.
- In App Router, prefer `searchParams`, `useSearchParams`, and `useRouter` for route-driven filters and pagination.
- Keep route segments, loading states, and error boundaries close to the feature they represent.
- Use nested layouts to share shell UI, not to hide page-specific logic.

## Project Structure

Use a feature-oriented structure unless the repo already follows another strong convention:

- `app/` for routes, layouts, loading, and error boundaries
- `components/` for reusable presentational pieces
- `features/` for domain-specific UI and hooks
- `services/` or `lib/` for API clients and shared helpers
- `types/` for shared contracts when local colocation is not better

## Next.js Platform Rules

- Use `next/link`, `next/image`, and `next/font` where appropriate instead of generic HTML replacements.
- Keep metadata and SEO close to the route.
- Respect caching and revalidation behavior intentionally. Do not cargo-cult cache settings.
- Avoid putting secret-bearing logic in client components.

## Ant Design Integration

- When using Ant Design in App Router, wire the official Ant Design Next.js registry pattern at the app root so styles render correctly during SSR.
- Keep Ant Design providers near the top-level layout and avoid duplicate provider trees.

## Source Notes

- Next.js documentation recommends Server Components and server-side data fetching as the default App Router model.
- Next.js documentation also treats client components as an explicit opt-in via `'use client'`.
- Official references:
  - [Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components)
  - [Fetching Data](https://nextjs.org/docs/app/getting-started/fetching-data)
