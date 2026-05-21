from typing import Optional

from core.llm_tool.router import LLMRouter
from core.loaders.txt_loader import load_txt
from custom_logger.logging_util import get_logger
from core.scanners.method_registry import OverloadConflict
from core.scanners.file_scanner import FunctionMeta


logger = get_logger(__name__)


def _extract_source(func: FunctionMeta) -> str:
    """
    Extract the raw source of a function from its file.
    Falls back to a signature summary if extraction fails.
    """
    try:
        lines = func.file_path.read_text(encoding="utf-8").splitlines()
        if func.source_lines:
            start, end = func.source_lines
            # Lines are 1-indexed in AST
            extracted = lines[start - 1 : end]
            return "\n".join(extracted)
    except Exception as e:
        logger.warning(f"Could not extract source for {func.qualified_name}: {e}")

    # Fallback: reconstruct from metadata
    args_str = ", ".join(
        f"{a.name}: {a.type_hint or 'Any'}"
        + (f" = {a.default!r}" if a.is_kwarg else "")
        for a in func.args
        if not a.is_variadic
    )
    doc = f'    """{func.docstring}"""' if func.docstring else ""
    return f"def {func.name}({args_str}):\n{doc}\n    ..."


def _build_analysis_prompt(conflict: OverloadConflict) -> str:
    """
    Build a structured prompt for LLM conflict analysis.
    """
    sections = []

    for i, func in enumerate(conflict.instances, 1):
        source = _extract_source(func)
        sections.append(
            f"### Instance {i}: `{func.module}.{func.name}`\n"
            f"**File:** `{func.file_path}`\n\n"
            f"```python\n{source}\n```"
        )

    joined = "\n\n".join(sections)

    txt_data = load_txt(path=PROMPT_PATH)
    prompt = txt_data.replace("{{function_name}}", conflict.function_name)
    prompt = prompt.replace("{{count_function}}", str(len(conflict.instances)))
    prompt = prompt.replace("{{function_details}}", joined)

    return prompt


async def analyze_conflicts(
    conflicts: list[OverloadConflict],
    config_path: Optional[str] = None,
    max_concurrent: int = 3,
) -> list[OverloadConflict]:
    """
    Run LLM analysis on all detected conflicts.

    Mutates each OverloadConflict in-place with:
      - llm_analysis (summary string)
      - merge_recommendation
      - similarity_score

    Returns the same list for chaining.

    Args:
        conflicts:       List of OverloadConflict from the registry.
        api_key:         Anthropic API key (falls back to ANTHROPIC_API_KEY env var).
        max_concurrent:  Max parallel API calls (rate limiting).
    """
    import asyncio

    semaphore = asyncio.Semaphore(max_concurrent)

    async def analyze_one(conflict: OverloadConflict) -> None:
        async with semaphore:
            logger.info(f"Analyzing conflict: '{conflict.function_name}'")
            prompt = _build_analysis_prompt(conflict)
            result = await _call_llm_async(prompt, config_path)

            if result:
                conflict.similarity_score = result.get("similarity_score")
                conflict.merge_recommendation = result.get(
                    "merge_recommendation", "review"
                )
                conflict.llm_analysis = _format_analysis(result)
            else:
                conflict.merge_recommendation = "review"
                conflict.llm_analysis = (
                    "_LLM analysis unavailable. Manual review required._"
                )

    await asyncio.gather(*[analyze_one(c) for c in conflicts])
    return conflicts


async def _call_llm_async(prompt: str, config_path: str) -> Optional[dict]:
    """Async wrapper around the synchronous Anthropic client."""
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _call_llm_sync(prompt, config_path))


def _call_llm_sync(prompt: str, config_path: str) -> Optional[dict]:
    """Synchronous version of the LLM call (runs in executor)."""
    import json

    client = LLMRouter(config_path=config_path)

    try:
        message = client.complete(prompt=prompt)
        raw = message.text.strip()

        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    except json.JSONDecodeError as e:
        logger.error(f"LLM returned invalid JSON: {e}")
    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
    return None


def _format_analysis(result: dict) -> str:
    """Format the LLM JSON result into a readable markdown block."""
    score = result.get("similarity_score", 0.0)
    summary = result.get("summary", "No summary provided.")
    rationale = result.get("merge_rationale", "")
    signature = result.get("suggested_merged_signature")

    badge = _score_badge(score)

    lines = [
        f"**Similarity:** {badge} `{score:.2f}`",
        "",
        f"**Analysis:** {summary}",
        "",
        f"**Recommendation:** {rationale}",
    ]

    if signature:
        lines += [
            "",
            "**Suggested merged signature:**",
            "```python",
            signature,
            "```",
        ]

    return "\n".join(lines)


def _score_badge(score: float) -> str:
    if score >= 0.7:
        return "🔴 HIGH"
    elif score >= 0.4:
        return "🟡 MEDIUM"
    else:
        return "🟢 LOW"
