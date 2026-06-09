# MCP Tool/Resource Handling Report

## Background

Codex and other MCP clients may probe `resources/list` and
`resources/templates/list` even when an MCP server is primarily tool-based.
For a tool-only server, empty resources are valid, but local models can
misinterpret that result and loop through resource discovery instead of calling
the available tools.

This project exposes most capabilities as MCP tools, such as `search_web`,
`fetch_url`, `browser_fetch`, paper utilities, model hub lookups, and local
file readers. The correct path for normal user requests is therefore tool
invocation, not `resources/read`.

## Changes Made

- Added explicit tool descriptions to every MCP tool.
- Added wording that tells clients and local models not to use
  `list_mcp_resources`, `list_mcp_resource_templates`, or `resources/read` for
  ordinary tool tasks.
- Kept `fetch_url(url, timeout)` as the primary URL-reading interface.
- Added a compatibility resource template for fetch:

```text
fetch://{encoded_url}
```

The `encoded_url` value is a percent-encoded URL, for example:

```text
fetch://https%3A%2F%2Fexample.com%2Farticle
```

This template is a fallback for clients that insist on resource reads. It does
not replace `fetch_url`.

## Community Notes

Community reports around Codex MCP usage describe a recurring pattern:

- the client or model calls `list_mcp_resources`;
- a tool-only server returns an empty resource list;
- the model keeps trying resource paths instead of calling tools;
- the user sees `Unknown resource` or repeated empty resource checks.

The practical guidance is:

- keep action-oriented capabilities as tools;
- write strong tool descriptions that include when to use the tool;
- explicitly say what not to call, especially `resources/read` for arbitrary
  URLs or files;
- add resource templates only as narrow compatibility fallbacks;
- use `enabled_tools` and tool approval settings in the Codex config to reduce
  tool noise.

## Operational Guidance

For normal web workflows:

1. Call `search_web` for discovery.
2. Call `fetch_url` for static pages returned by search.
3. Call `browser_fetch` when JavaScript rendering or browser cookies are
   required.
4. Avoid MCP resource discovery unless the server advertises a concrete
   resource/template that matches the task.

For local files, prefer the appropriate tool:

- `read_local_file`, `list_local_files`, `search_local_files`
- `classify_readable_file`, `read_pdf_file`, `ocr_image_file`

Do not use MCP resources for arbitrary local paths unless a server explicitly
exposes a resource template for that purpose.

## Verification

The change was verified with:

```text
ruff check servers tests/test_fetch_server.py
pytest
```

Results:

```text
All checks passed
132 passed
```
