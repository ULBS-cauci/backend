# LLM connection via OpenAI SDK

This module implements the LLM (Large Language Model) communication layer for
the AI Tutor backend. The goal is to let any other part of the app call an LLM
through an abstract interface, without depending on a specific provider
(OpenAI, Anthropic, Ollama, etc.).

---

## What I built

**`LLMInterface`** (`app/data_access/interfaces/llm.py`) — an abstract class
that defines two async methods every LLM client must implement:

- `generate(messages)` — sends the messages and returns the full response as
  a string.
- `stream(messages)` — sends the messages and yields the response chunk by
  chunk, as it's being generated.

**`OpenAILLMClient`** (`app/data_access/clients/openai_client.py`) — the
concrete implementation. It uses the official `openai` SDK to actually talk
to OpenAI's API. It also has a small helper `_to_openai` that converts our
`ChatMessage` objects into the dict format OpenAI expects.

I split the two so the rest of the app (services, routers) only depends on
`LLMInterface`. If we later want to use Anthropic or Ollama, we just add a
new client (e.g. `AnthropicLLMClient`) that implements the same interface —
nothing else in the app changes.

---

## Installation

> `activate .venv`

> `pip install -r requirements.txt`

## .env

Add to your `.env`:

```
LLM_CLIENT_TYPE=openai
OPENAI_API_KEY=sk-proj-...
```
