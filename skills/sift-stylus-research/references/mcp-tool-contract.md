# MCP Tool Contract: `search_stylus_docs`

## Purpose
Retrieve relevant Arbitrum Stylus documentation context before composing technical answers.

## Tool name
`search_stylus_docs`

## Input schema
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Natural language query describing the technical Stylus question."
    }
  },
  "required": ["query"]
}
```

## Invocation policy
- Call this tool for technical Stylus questions.
- Prefer at least one tool call before final answer generation.
- If output indicates no relevant context, state that limitation explicitly.
- Treat `agent_guidance` as normative behavior.
- Default behavior is references-first and code-generation-disallowed.

## Backend mapping
- Hosted backend endpoint: `POST /skills/sift-stylus-research/search`
- Request body:
```json
{ "prompt": "<query>" }
```

## Expected response shape
```json
{
  "found": true,
  "context": "...",
  "chunks_used": 4,
  "query_mode": "tooling",
  "agent_guidance": {
    "behavior": "references_first",
    "code_generation": "disallowed",
    "instructions": ["..."]
  },
  "references": [
    { "title": "...", "url": "...", "source": "..." }
  ]
}
```

or

```json
{
  "found": false,
  "context": "",
  "reason": "No relevant Stylus documentation was found for this query.",
  "agent_guidance": {
    "behavior": "references_first",
    "code_generation": "disallowed",
    "instructions": ["..."]
  },
  "references": []
}
```

## Consumer guidance
- Treat `context` as source material.
- Cite retrieved details in answers.
- Do not fabricate APIs not in tool output.
- Do not generate contract/app code unless explicitly overridden by user intent.
