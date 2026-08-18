# Revision report data

Use this schema only after the user explicitly asks for a visual revision report:

```json
{
  "title": "Optional heading",
  "original": "The exact original prose.",
  "revised": "The exact revised prose.",
  "changes": [
    {"type": "keep", "text": "Text present unchanged in both versions."},
    {"type": "delete", "text": "Text removed.", "reason": "Why it was removed."},
    {
      "type": "rewrite",
      "before": "Original wording.",
      "after": "Revised wording.",
      "reason": "Why it changed."
    }
  ]
}
```

`title` is optional. All other top-level fields are required. Changes are ordered and lossless:

- Concatenating every `keep.text`, `delete.text`, and `rewrite.before` in order must equal
  `original` byte-for-byte after JSON decoding.
- Concatenating every `keep.text` and `rewrite.after` in order must equal `revised` byte-for-byte.
- An insertion is a `rewrite` with an empty `before`; a replacement with an empty `after` is
  permitted, although `delete` is clearer for a pure deletion.
- Every deletion and rewrite needs a concise reason grounded in the actual edit.

The bundled builder enforces these invariants. Do not approximate omitted text with ellipses.
