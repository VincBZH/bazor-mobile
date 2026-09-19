PROJECT: BAZOR Identity Self-Test
REQUEST_ID: MAMMOUTH-IDENTITY-SELFTEST-20260919
TARGET_AGENT: mammouth

TASK:
Return your BAZOR agent identity and distinguish it from your underlying model.

RESPONSE_FORMAT:
AGENT_ID: mammouth
PROVIDER: mammouth
UNDERLYING_MODEL: <actual model if known, else unknown>
ROLE: independent_external_reviewer
IDENTITY_OK: true

Forbidden:
- AGENT_ID: gpt
- AGENT_ID: ollama
- claiming that the underlying model name changes the BAZOR agent identity.