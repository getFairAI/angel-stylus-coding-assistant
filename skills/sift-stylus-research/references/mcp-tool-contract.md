# MCP Tool Contract: `search_stylus_code`

## Purpose
Retrieve relevant Arbitrum Stylus documentation context before composing **small, practical Stylus code snippets and examples** (patterns, “how do I implement X” guidance), with **sources-first** behavior and safe adaptation notes.

This contract is intended to support the **stylus-code-helper** skill.

## Tool name
`search_stylus_code`

## Input schema
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Natural language query describing the Stylus code example, snippet, or implementation pattern needed."
    }
  },
  "required": ["query"]
}
```

## Invocation policy
- Call this tool for:
  - Requests for Stylus code snippets or implementation examples.
  - “How do I do X in Stylus?” questions where a snippet helps (storage, calls, ABI, events/logs, precompiles, host I/O).
  - Pattern-level translations (e.g., Solidity → Stylus Rust) where code fragments illustrate the mapping.
  - Code-level optimization guidance when sources can support the recommended changes.
- Prefer at least one tool call before generating code.
- If output indicates no relevant context:
  - State that no supporting documentation was found.
  - Provide conservative guidance only.
  - Any code provided must be clearly labeled **“Illustrative (not source-backed)”**.
  - Include a **Retrieval limitation** note.
- Treat `agent_guidance` as normative behavior.
- Default behavior is references-first and snippet-oriented code generation (not full contracts unless explicitly requested).

## Backend mapping
- Hosted backend endpoint: `POST /skills/sift-stylus-code-helper/search`
- Request body:
```json
{ "prompt": "<query>" }
```

## Expected response shape

### Case: Relevant documentation found
```json
{
  "found": true,
  "context": "...",
  "chunks_used": 4,
  "query_mode": "code_pattern",
  "agent_guidance": {
    "behavior": "references_first",
    "code_generation": "allowed",
    "max_snippet_size_lines": 80,
    "full_contracts": "on_request_only",
    "instructions": ["..."]
  },
  "references": [
    { "title": "...", "url": "...", "source": "..." }
  ]
}
```

### Case: No relevant documentation found
```json
{
  "found": false,
  "context": "",
  "reason": "No relevant Stylus documentation was found for this query.",
  "agent_guidance": {
    "behavior": "references_first",
    "code_generation": "allowed",
    "max_snippet_size_lines": 80,
    "full_contracts": "on_request_only",
    "instructions": ["..."]
  },
  "references": []
}
```

## Consumer guidance
- Treat `context` as source material for snippet creation.
- Cite retrieved details in answers via a **References** section using the tool’s `references` URLs.
- Do not fabricate SDK APIs, CLI flags, host functions, or deployment commands not present in tool output.
- Generate **small, composable snippets** by default:
  - Prefer a single primary snippet, optionally 1–2 variants.
  - Keep within `max_snippet_size_lines`.
- Do not generate full contracts or multi-file scaffolds unless:
  - The user explicitly requests it, and
  - `agent_guidance.full_contracts` allows it (e.g., `on_request_only`), and
  - Any unsourced portions are clearly marked as such.
- Mark uncertainty clearly when signatures or exact APIs are not included in retrieved context.