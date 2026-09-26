# shadcn/ui vocabulary for blueprints and reviews

The default stack is React with shadcn/ui (Radix primitives, Tailwind, lucide icons). A project is
shadcn when it has `components.json` or a `components/ui/` folder with files such as `button.tsx`
and `card.tsx`. Name zones with these components so a blueprint can be built without translation.
The project's own `components/ui/` files win over this list: shadcn components are copied into the
app and are often edited.

## Take inventory first

A `components.json` does not mean the components exist. Many projects install a handful and
build the rest by hand. Before naming components in a blueprint or a review:

- List `components/ui/`. Only those components are installed.
- Check which Radix packages the code imports, not just which `package.json` lists. Unused
  dependencies are common.
- Note the project's own component folder (for example `components/<app>/`) and what it covers:
  page headers, empty states, callouts, stat tiles.

Then mark every component a proposal names:

- *installed*: already in `components/ui/`;
- *add*: `npx shadcn add <name>`, then restyle it to the project's tokens;
- *the project's own*: an existing component that already does the job.

When the project uses only a few shadcn components, recommend a middle path. Take behavior
from shadcn's components, which build on Radix, vaul, cmdk, and sonner, because focus, keyboard,
and dismissal are hard to get right: `Dialog`, `AlertDialog`, `Sheet`, `Drawer`, `DropdownMenu`,
`Popover`, `Tooltip`, `Tabs`, `ToggleGroup`, `Select`, `Command`, and `Sonner`. Keep
presentation that is specific to the product in its own components. Never propose a new
hand-built dialog, menu, or tooltip.

## Read the project's variants before counting primaries

Stock `button.tsx` defines `default` (filled, the primary), `destructive`, `outline`, `secondary`,
`ghost`, and `link`, with sizes `default`, `sm`, `lg`, and `icon`. Many apps rename them. For
example, `default` may be restyled as an outline and a new `primary` becomes the filled button.
Open `components/ui/button.tsx`, find the `cva` variant whose classes set a solid background
(`bg-primary`, `bg-ink`, …), and treat that variant as "filled" in every rule below. Count raw
`<button className="bg-…">` elements too.

## Zone → component

| Zone | shadcn building blocks | Notes |
|---|---|---|
| App frame | `SidebarProvider` › `AppSidebar` + `SidebarInset` | The sidebar-07/-08 blocks are the reference shape |
| Scope switcher (workspace, project) | `SidebarHeader` with a `DropdownMenu` team/project switcher | Scope that changes every page's data lives here or in the breadcrumb, not among header stats |
| Navigation | `SidebarGroup` › `SidebarGroupLabel` › `SidebarMenu` › `SidebarMenuButton isActive` | `tooltip` equals the label when `collapsible="icon"` |
| Account, theme, sign out | `SidebarFooter` › `NavUser` dropdown | Sign out belongs here, not only on a settings page |
| Page header | `header` with `SidebarTrigger`, `Separator`, `Breadcrumb` (`BreadcrumbLink`, `BreadcrumbPage`), then the page's `h1` and its actions | `BreadcrumbPage` text = nav label = `h1` = document title |
| Status beside the title | `Badge` | Not a card chip far from the title |
| Primary content | `Card`, `Table` or a TanStack `DataTable`, `Tabs` | `Tabs` only for independent sections (see `layouts.md`) |
| Row and overflow actions | `DropdownMenu` on a ghost icon `Button` with `MoreHorizontal` and a `sr-only` label | Destructive items last, `variant="destructive"` |
| Anything that goes to another page | `<Button asChild><Link …>` with the router's `Link` | Never `onClick={() => navigate(…)}`: a `<button>` cannot open in a new tab or be copied as a link |
| Destructive confirmation | `AlertDialog` (`AlertDialogAction` with the specific verb, `AlertDialogCancel`) | Never `Dialog` with OK |
| Short task that keeps context | `Dialog`; side editing `Sheet`; phones `Drawer` | A dialog with tabs or scrolling is a page |
| Empty state | `Empty` (`EmptyHeader`, `EmptyMedia`, `EmptyTitle`, `EmptyDescription`, `EmptyContent`) | One primary action inside `EmptyContent` |
| Loading | `Skeleton` in the shape of the ideal state; `Spinner` inside the triggering button | See `states.md` |
| Error | `Alert variant="destructive"` with `AlertTitle`, `AlertDescription`, and a Retry `Button` | Say what failed; keep what loaded |
| Success feedback | `sonner` `toast()` plus an in-place change | A toast alone can be missed |
| Forms | `Form`, `FormField`, `FormItem`, `FormLabel`, `FormControl`, `FormDescription`, `FormMessage` (or the newer `Field` family) with zod | Single column; see `archetypes.md` › Form |

## Responsive rules in Tailwind

- Mobile is the base style; breakpoints add columns: `grid gap-4 md:grid-cols-2 xl:grid-cols-4`.
  A bare `grid-cols-2` or `grid-cols-3` with no base is a finding: it squeezes columns at 390 px
  and clips buttons inside `overflow-hidden` parents.
- A row that holds text and actions wraps: `flex flex-wrap items-center gap-2`. The text is
  `min-w-0 flex-1`. A `shrink-0` action group needs the row to wrap below `sm`, or the text
  collapses to one word per line.
- The shadcn sidebar becomes an off-canvas `Sheet` below 768 px (`useIsMobile`). The page must
  still show location, so keep `SidebarTrigger` and the breadcrumb in the header.
- Use one content width per archetype, for example `mx-auto w-full max-w-6xl` for lists and
  dashboards and `max-w-2xl` for forms. Set it in the layout, not per page.
- Sticky headers (`sticky top-0`) that wrap to two rows on phones cost a tenth of the screen.
  Hide stats and secondary badges below `sm`.

## Headings and titles

- Current shadcn `CardTitle` and `CardDescription` render `div`s with `data-slot`. A page
  therefore needs an explicit `<h1>` in its header. A card title that heads a section needs a real
  heading: render an `<h2>` inside it, or change `card.tsx`.
- Set a document title per route. With React 19, render `<title>` in the page (React hoists it).
  In Next.js, use `metadata` or `generateMetadata`. In React Router, use route `meta` or a
  `handle` read by the layout.
- Markdown rendered inside a page (for example with `react-markdown`) must not introduce an `h1`.
  Map Markdown headings to `h3` or lower.
- `SidebarInset` renders `<main>`. A page inside it must not add another `<main>`: use a `div`
  or `section`.

Sources: shadcn/ui documentation (components, blocks `sidebar-07`, theming, `components.json`);
Radix Primitives documentation; Tailwind CSS responsive design; React 19 `<title>` support; WCAG
2.2 (2.4.2 Page titled, 1.3.1 Info and relationships, 2.5.8 Target size); Vercel Web Interface
Guidelines (links for navigation).
