import argparse
import asyncio
from typing import Optional

from custom_logger.logging_util import get_logger
from importlib.resources import files

from core.scanners.method_registry import Registry
from core.scanners.repository_scanner import scan_repository

logger = get_logger(__name__)

CONFIG_PATH = str(files("holistiq").joinpath("config/config_llm.yaml"))
PROMPT_PATH = str(files("holistiq").joinpath("prompts/code_repo_analyser_v0.txt"))


#  TODO needs to get added to holistiq cli. Not Priority
def analyse_code_repo(
    repo_path: str,
    config_path: Optional[str] = None,
    llm_analyse: bool = False,
    llm_concurrent: int = 3,
    sys_prompt: Optional[str] = None,
) -> None:
    """Scan, analyze conflicts with LLM, and generate documentation."""

    logger.info(f"Scanning: {repo_path}")
    results = scan_repository(repo_path)
    registry = Registry()
    registry.build(results)

    if registry.has_conflicts and llm_analyse:
        logger.info("starting llm analyse for conflicting methods")
        from core.scanners.method_conflict_detector_llm import analyze_conflicts

        asyncio.run(
            analyze_confli cts(
                conflicts=registry.conflicts,
                config_path=config_path or CONFIG_PATH,
                max_concurrent=llm_concurrent,
                sys_prompt=sys_prompt or PROMPT_PATH,
            )
        )


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_PATH, help="Path to LLM config YAML")
    parser.add_argument("--sysprompt", default=CONFIG_PATH, help="Path to system prompt file")
    parser.add_argument("--llm_analyse", type=lambda x: x.lower() == "true", default=False, help="Whether to perform LLM analysis on conflicts")
    parser.add_argument("--llm_concurrent", type=int, default=1, help="Number of concurrent LLM requests")
    parser.add_argument("repo_path", help="Path to the code repository to analyze")

    return parser.parse_args()


if __name__ == "__main__":

    args = _parse_args()
    print(f"Arguments: {args}")
    analyse_code_repo(
        repo_path=args.repo_path,
        config_path=args.config,
        llm_analyse=args.llm_analyse,
        llm_concurrent=args.llm_concurrent,
        sys_prompt=args.sysprompt,
    )
