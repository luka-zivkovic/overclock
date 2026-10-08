# Notion-flavored Markdown, the parts a feature page needs

Notion's connector and API read a Markdown variant. The differences from GitHub Markdown are
what break pages, so follow these rules exactly. The full specification is the MCP resource
`notion://docs/enhanced-markdown-spec`, readable with the connector's `fetch` tool.

## Structure

- Do not put the title in the content; set it through the page `title` property.
- Children are indented with **tabs**, never spaces. A clip under a numbered step is a tab-indented
  line below that step.
- Empty lines are stripped. Notion spaces blocks itself; never write `<empty-block/>` to fake
  spacing.
- Outside code blocks, escape these characters with a backslash when you mean them literally:
  `\ * ~ ` $ [ ] < > { } | ^`. Inside code blocks, write everything literally.

## Blocks

| Block | Syntax |
|---|---|
| Heading | `## Walkthrough` (levels 1 to 3; 4 exists, 5 and 6 collapse to 4) |
| Paragraph | plain text line |
| Numbered step | `1. Click **New suite**. A dialog asks for a name.` |
| Bullet | `- text` (never an empty bullet) |
| Image or GIF | `![Caption](URL)` on its own line; uploads use the `suggested_markdown` the upload returned |
| Callout | `<callout icon="⚠️" color="yellow_bg">` then tab-indented children, then `</callout>` |
| Toggle | `<details>` / `<summary>Title</summary>` / children / `</details>` |
| Toggle heading | `## Advanced {toggle="true"}` with tab-indented children |
| Table | `<table header-row="true">` with `<tr>` rows of `<td>` cells; cells hold rich text only |
| Columns | `<columns>` / `<column>` children `</column>` / `</columns>` |
| Divider | `---` |
| Code | fenced block with a language |
| Quote | `> text` (one line; `<br>` for a line break inside it) |
| Table of contents | `<table_of_contents/>` |

## Inline

`**bold**`, `*italic*`, `` `code` ``, `[text](https://url)`,
`<mention-page url="https://www.notion.so/<id>">Title</mention-page>` for an internal page,
`<mention-date start="2026-10-07"/>` for a date. Use a Markdown link only for external URLs.

Colors, when needed: `{color="gray"}` at the end of a block, or `<span color="red">text</span>`
inline. Background variants end in `_bg`.

## A worked step with a clip

```text
## Walkthrough

1. Open **Suites** and click **New suite**. A dialog asks for a name.
	![Click New suite; the Create a suite dialog opens](file-upload://...)
2. Type the name and click **Create suite**. The dialog closes and a toast confirms it.
	![The new suite appears at the top of the list](file-upload://...)
```

## Pitfalls

- `<page url="...">` **moves** an existing page into this one. Reference pages with
  `<mention-page>`.
- Headings inside table cells, images inside tables, and nested lists deeper than two levels do
  not render as intended.
- A `>` on its own line, or an empty `- `, renders as an empty block.
- Local paths like `clips/name.gif` are not resolved; every clip must be uploaded first.
