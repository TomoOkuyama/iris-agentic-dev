"""Which model an eval session runs on, how it is reached and what it costs.

A model is `<provider>/<id>`. opencode computes a session's cost from the prices declared for the model
in its config, so a model with no declared price would record every session as free and break the
spend accounting. Each model the evals may use is therefore listed here with its prices, and a model
that is not listed is refused instead of guessed.

`bedrock-oai/...` is an OpenAI model on Amazon Bedrock, reached through Bedrock's OpenAI-compatible
endpoint with the long-term Bedrock key that `bclaude` uses (`AWS_BEARER_TOKEN_BEDROCK`, from
`~/.secrets.env`). The Converse route does not carry reasoning effort through opencode's Bedrock SDK,
which rejects the `redactedContent` stream block; this route does.
"""

from __future__ import annotations

BEDROCK_REGION = "us-east-1"
BEDROCK_OPENAI_URL = f"https://bedrock-runtime.{BEDROCK_REGION}.amazonaws.com/openai/v1"

#: Dollars per million tokens, from opencode's catalogue for the same OpenAI model. Bedrock's own rate
#: for it was not checked, so cost figures for these models are list-price figures.
PRICES = {
    "global.openai.gpt-6-luna": {
        "input": 0.1,
        "output": 0.5,
        "cache_read": 0.01,
        "cache_write": 0.125,
    },
}

CREDENTIAL_ENV = {"openai": "OPENAI_API_KEY", "bedrock-oai": "AWS_BEARER_TOKEN_BEDROCK"}


class UnknownModel(ValueError):
    """The model or provider is not one this harness knows how to reach and price."""


class MissingCredential(RuntimeError):
    """The environment holds nothing that authenticates the model."""


def split_model(model: str) -> tuple[str, str]:
    provider, _, model_id = (model or "").partition("/")
    return provider, model_id


def api_key_for(model: str, env) -> str:
    provider, _ = split_model(model)
    name = CREDENTIAL_ENV.get(provider)
    if name is None:
        raise UnknownModel(f"{model!r} names a provider this harness cannot reach")
    key = env.get(name)
    if not key:
        hint = (
            " Source ~/.secrets.env first; it holds the long-term key bclaude uses."
            if provider == "bedrock-oai"
            else ""
        )
        raise MissingCredential(
            f"{name} is not set, so every session on {model} would fail to start and score as a "
            f"failure of the arm.{hint}"
        )
    return key


def provider_block(model: str, api_key: str, effort: str | None = None) -> dict:
    """The `provider` section of the opencode config for `model`."""
    provider, model_id = split_model(model)
    if provider == "openai":
        if effort is not None:
            raise UnknownModel(
                "effort is only wired for Bedrock OpenAI models; the openai route would ignore it "
                "and the run would be labelled with a setting it did not use"
            )
        return {"openai": {"options": {"apiKey": api_key}}}
    if provider == "bedrock-oai":
        prices = PRICES.get(model_id)
        if prices is None:
            raise UnknownModel(
                f"{model_id!r} has no declared price, so its sessions would be recorded as free. "
                f"Known: {', '.join(sorted(PRICES))}"
            )
        entry = {
            "name": model_id,
            "tool_call": True,
            "reasoning": True,
            "limit": {"context": 400000, "output": 32000},
            "cost": dict(prices),
        }
        if effort:
            entry["options"] = {"reasoningEffort": effort}
        return {
            "bedrock-oai": {
                "npm": "@ai-sdk/openai",
                "name": "Bedrock OpenAI",
                "options": {
                    "baseURL": BEDROCK_OPENAI_URL,
                    "apiKey": "{env:AWS_BEARER_TOKEN_BEDROCK}",
                },
                "models": {model_id: entry},
            }
        }
    raise UnknownModel(f"{model!r} names a provider this harness cannot reach")


DEFAULT_PORT = "52780"
DEFAULT_CONTAINER = "iris-dev-iris"


def localize_prompt(prompt: str, *, web_port: str, container: str) -> str:
    """Point a task's prompt at the container this run uses.

    The tasks name the main dev container and its port. A run beside others uses its own container, and
    an agent that follows the prompt would edit the main one and be graded against the other. Left
    alone when the run uses the defaults, so existing runs read byte for byte as before.
    """
    if str(web_port) != DEFAULT_PORT:
        prompt = prompt.replace(f"web port {DEFAULT_PORT}", f"web port {web_port}")
    if container != DEFAULT_CONTAINER:
        prompt = prompt.replace(DEFAULT_CONTAINER, container)
    return prompt
