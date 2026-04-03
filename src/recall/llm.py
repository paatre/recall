import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from openai import OpenAI

from recall.collectors.base import Event


def get_gh_token() -> str:
    """Retrieve the GitHub authentication token using the gh CLI."""
    gh_path = shutil.which("gh")
    if not gh_path:
        msg = "The 'gh' CLI is not installed or not in PATH."
        raise RuntimeError(msg)
    try:
        result = subprocess.run(  # noqa: S603
            [gh_path, "auth", "token"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        msg = (
            "Failed to get GitHub token via 'gh auth token'. Ensure you are logged in."
        )
        raise RuntimeError(msg) from e


def load_prompt_template() -> str:
    """Load the timesheet prompt from the external markdown file."""
    prompt_path = Path(__file__).parent / "prompts" / "timesheet.md"
    try:
        return prompt_path.read_text()
    except FileNotFoundError as e:
        msg = f"Prompt file not found at {prompt_path}"
        raise RuntimeError(msg) from e


def generate_timesheet(  # noqa: C901
    events: list[Event],
    target_date: str,
    llm_config: dict[str, Any],
    model: str | None = None,
) -> list[dict[str, Any]]:
    """Generate a grouped timesheet using an LLM."""
    provider = llm_config.get("provider", "github")
    api_key = llm_config.get("api_key", "")
    base_url = llm_config.get("base_url", "")
    custom_instructions = llm_config.get("custom_instructions", "")

    if provider == "github":
        if not api_key:
            api_key = get_gh_token()
        base_url = base_url or "https://models.inference.ai.azure.com"
        model_name = model or "gpt-4o"
    elif provider == "openai":
        base_url = base_url or "https://api.openai.com/v1"
        model_name = model or "gpt-4o"
    elif provider == "custom":
        if not base_url:
            msg = "A base_url is required when provider is 'custom'"
            raise RuntimeError(msg)
        model_name = model or "gpt-4"
    else:
        msg = f"Unknown llm provider: {provider}"
        raise RuntimeError(msg)

    client = OpenAI(
        base_url=base_url if base_url else None,
        api_key=api_key if api_key else None,
    )
    prompt_template = load_prompt_template()

    # Create a mapping of event IDs to Events
    event_map = dict(enumerate(events))
    event_lines = []

    for i, e in event_map.items():
        time_str = e.timestamp.astimezone().strftime("%H:%M:%S")
        duration = f"{e.duration_minutes}m" if e.duration_minutes else ""
        line = f"[ID: {i}] [{time_str}] {e.source} - {e.description} {duration}"
        event_lines.append(line)

    chunk_size = 150
    chunks = [
        event_lines[i : i + chunk_size] for i in range(0, len(event_lines), chunk_size)
    ]

    all_timesheet_blocks = []

    for chunk in chunks:
        events_text = "\n".join(chunk)

        prompt = prompt_template.format(
            target_date=target_date,
            events_text=events_text,
            custom_instructions=custom_instructions,
        )

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that outputs "
                    "only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        content = response.choices[0].message.content
        if content:
            try:
                data = json.loads(content)
                blocks = data.get("timesheet", [])

                for block in blocks:
                    block["_events"] = [
                        event_map[eid]
                        for eid in block.get("event_ids", [])
                        if eid in event_map
                    ]

                all_timesheet_blocks.extend(blocks)
            except json.JSONDecodeError:
                pass

    return all_timesheet_blocks
