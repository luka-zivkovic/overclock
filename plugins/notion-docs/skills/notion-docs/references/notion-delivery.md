# Delivering the page to Notion

The local bundle in `notion-docs-output/<slug>/` is always written first: `page.md` in
Notion-flavored Markdown with `![caption](clips/<name>.gif)` references, and the clips with their
manifests. Publishing moves that bundle into Notion by one of three paths, in this order of
preference.

## Destination

- The user named a page: create the new page as a child of it (parent `page_id`), or, when the
  user said to put the content on that page itself, insert at the end of it.
- No destination named: create the page with `creation_mode: "draft"`, which makes a private
  workspace-level page, and tell the user it is private and can be moved.
- Never `replace_content` on a page that has child pages or databases, and never place a `<page>`
  tag that points at an existing page: that moves it.

## Path A: the Notion connector (MCP tools `create-file-upload`, `create-pages`, `update-page`, `fetch`)

Upload the clips right before creating the page; an upload that is not placed on a page expires
after about an hour, and the upload URL itself is short-lived.

1. For each clip whose manifest says `ok`, call `create-file-upload` with
   `{"filename": "<name>.gif"}`. The result gives `upload_url` and `upload_headers`.
2. Send the file with one multipart POST, passing every returned header:

   ```text
   curl -sS -X POST "<upload_url>" \
     -H "<header-name>: <header-value>" ... \
     -F "file=@clips/<name>.gif;type=image/gif"
   ```

   The response includes `markdown_source` and `suggested_markdown`. The headers carry a bearer
   token: pass them straight to `curl`, and do not write them into `publish.json`, the page, or
   any log in the bundle.
3. In the page content, replace each `![caption](clips/<name>.gif)` line with the upload's
   `suggested_markdown`, keeping the indentation that nests it under its step. The connector
   currently returns `<image src="file-upload://<id>"></image>`; put the caption between the
   tags, `<image src="file-upload://<id>">Caption</image>`, and it renders as the image caption
   (verified by fetching the page back, which shows `![Caption](notion-file-block://...)`). If the
   shape changes, use whatever is returned and keep the caption as its text or alt text.
4. Create the page with `create-pages` (`parent: {"type": "page_id", "page_id": "..."}`,
   `properties: {"title": "<Feature name>"}`, `content: <page markdown>`), or append to an existing
   page with `update-page` and `command: "insert_content"`, `position: {"type": "end"}`.
   Set `allow_async: false` so the page is ready for verification.
5. `fetch` the new page. Check: one image block per clip, no literal `clips/` path left in the
   text, the first paragraph is the job sentence, no empty list items or stray tags.
6. Write `publish.json` into the bundle: page URL, title, each clip's name and upload id, the
   timestamp. No headers, no tokens.

Single-part uploads are limited to 20 MiB and free workspaces to 5 MiB per file; the recorder flags
GIFs over 8 MiB as `too_large` before you get here. A GIF placed as an image block plays inline in
Notion, which is why clips are GIFs and not video blocks: video blocks do not autoplay.

## Path B: the Notion API with `NOTION_TOKEN` in the environment

Use this when no connector is available but the user has an internal integration token and has
shared the destination page with that integration. The token comes only from the environment.

```text
# 1. create the upload
curl -sS https://api.notion.com/v1/file_uploads \
  -H "Authorization: Bearer $NOTION_TOKEN" -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{"filename": "<name>.gif", "content_type": "image/gif"}'
# -> {"id": "<upload-id>", "upload_url": "https://api.notion.com/v1/file_uploads/<upload-id>/send", ...}

# 2. send the bytes
curl -sS -X POST "https://api.notion.com/v1/file_uploads/<upload-id>/send" \
  -H "Authorization: Bearer $NOTION_TOKEN" -H "Notion-Version: 2022-06-28" \
  -F "file=@clips/<name>.gif;type=image/gif"
# -> status "uploaded"

# 3. append the image block to the page
curl -sS -X PATCH "https://api.notion.com/v1/blocks/<page-id>/children" \
  -H "Authorization: Bearer $NOTION_TOKEN" -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{"children": [{"type": "image", "image": {"type": "file_upload", "file_upload": {"id": "<upload-id>"},
       "caption": [{"type": "text", "text": {"content": "<caption>"}}]}}]}'
```

Newer `Notion-Version` values change the file block shape; if the request is rejected, check the
current File Upload reference rather than guessing. The page text itself is pasted from `page.md`
in the Notion UI (Notion converts pasted Markdown into blocks) or appended block by block with the
same `PATCH` endpoint.

## Path C: hand over the bundle

When neither path is available, give the user `notion-docs-output/<slug>/` and three lines:

1. Create the page and paste the text of `page.md` into it.
2. Drag each `clips/<name>.gif` onto the page where its `![...]` line is.
3. Delete the `![...]` placeholder lines.

## Report

After any path, tell the user: the page URL or bundle path, each clip's name, length, and size,
what the page says was not verified or not shown, the output directory, and that it belongs in
`.gitignore` if it is not already ignored.
