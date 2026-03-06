# Ideas & Future Work

## Secure credential management from the agent chat interface

### What is MCP Elicitation?

Elicitation (spec 2025-06-18) is a first-class MCP primitive that lets a server
request structured input from the user **through the client**, during a tool's
execution, without the data passing through the LLM context.

Flow:
```
Server ──elicitation/create──► Client
                               Client shows a native UI widget (form, dialog…)
                               User fills in the field(s)
Client ──ElicitResult──────────► Server
Server continues tool execution with the data
```

The value never appears in the LLM conversation history. It goes JSON-RPC
directly server ↔ client.

### On encryption

No specific crypto layer is added by Elicitation. Security relies on:
- The transport itself (local stdio = in-memory only; HTTP = HTTPS)
- Client isolation (the widget is rendered by the IDE, not the chat box)

**Important**: The spec explicitly states:
> "Servers MUST NOT use elicitation to request sensitive information."

Elicitation is NOT designed for passwords. The JSON Schema subset it supports
has no `password` field type (masked input). The client may log elicited values.

### Two elicitation modes in mcp 1.26.0

Our current SDK already has both:

| Mode | Type | Use case |
|------|------|----------|
| Form | `ElicitRequestFormParams` | Flat JSON Schema → rendered form: string, int, bool, enum |
| URL  | `ElicitRequestURLParams`  | Server sends a URL → client opens it in browser (OAuth!) |

Server-side API (`mcp` SDK 1.26.0):
```python
from pydantic import BaseModel
from mcp.server.fastmcp import Context

class TokenInput(BaseModel):
    token: str

@mcp.tool
async def admin_token_refresh(ctx: Context) -> str:
    result = await ctx.elicit(
        "Paste your new TICKTICK_API_TOKEN (from TickTick → Settings → Integrations → API)",
        schema=TokenInput,
    )
    if result.action != "accept":
        return "Cancelled."
    _write_env("TICKTICK_API_TOKEN", result.content["token"])
    return "Token updated."
```

### What we CAN build (within spec)

Allowed (not "sensitive information"):
- Confirmation dialogs (approve/decline, no data)
- Username / email field (not a password)
- Raw token paste — a token is not a memorized secret in the password sense,
  it's an opaque string the user copies. Arguable, but defensible.

Not allowed by spec:
- Collecting passwords directly

Interesting with URL elicitation:
- Open the TickTick developer page so the user generates their PAT, then
  return the token via a follow-up form elicitation.

### Client support status (March 2026)

| Client | Server-side SDK | Client-side handler |
|--------|----------------|---------------------|
| mcp Python 1.26.0 | ✅ `ctx.elicit()` | ✅ implemented |
| VS Code Copilot Chat | — | ❓ unclear, spec is recent (2025-06-18) |
| Claude Desktop | — | Partial (opt-in) |

PR #2343 (active, draft) clarifies that remote servers implementing elicitation
SHOULD require MCP authorization to prevent phantom task injection via leaked
session IDs. A H1 bug bounty PoC (non-compliant server) demonstrated this risk.

### Security threat: why remote elicitation needs MCP auth

Without auth, a malicious actor who obtains a session ID can craft an
`elicitation/create` request that impersonates the server. The client has no
way to verify the server identity → user fills in a fake form.

MCP auth (OAuth2 PKCE as defined in the spec) binds the session to a verified
identity. The spec currently says SHOULD; PR #2343 proposes upgrading to MUST.

### When to implement

Implement `admin_token_set` / `admin_session_set` as MCP tools using Elicitation when:
- [ ] VS Code Copilot Chat confirms client-side elicitation handler support
- [ ] A live test (`admin_test_elicitation` tool returning the value back) succeeds
- [ ] For remote deployment: MCP auth (OAuth2 PKCE) is implemented first

### How to test now

A minimal probe tool can be added to server.py to see if VS Code handles
`elicitation/create` or returns `ElicitationRequiredError`:

```python
from pydantic import BaseModel

class Probe(BaseModel):
    value: str

@mcp.tool
async def admin_test_elicitation(ctx: Context) -> str:
    """Test whether this MCP client supports elicitation."""
    try:
        result = await ctx.elicit("Type anything to test elicitation:", schema=Probe)
        if result.action == "accept":
            return f"Elicitation works. You typed: {result.content['value']}"
        return f"Elicitation supported but user {result.action}d."
    except Exception as e:
        return f"Elicitation not supported by this client: {e}"
```

