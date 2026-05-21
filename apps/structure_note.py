import argparse
import sys

from core.llm_tool.router import LLMRouter
from core.loaders.txt_loader import load_txt
from custom_logger.logging_util import get_logger
from importlib.resources import files


logger = get_logger(__name__)

CONFIG_PATH = str(files("holistiq").joinpath("config/config_llm.yaml"))
PROMPT_PATH = str(files("holistiq").joinpath("prompts/notes_structure_tasks_v0.txt"))


def structure_notes_to_tasks(
    user_input: str,
    config_path: str,
    prompt_path: str,
):
    logger.info("starting structure_notes_to_tasks...")
    txt_data = load_txt(path=prompt_path)
    prompt = txt_data.replace("{{input}}", user_input)
    output = LLMRouter(config_path)
    output = output.complete(prompt=prompt)
    return output


def _parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_PATH, help="Path to LLM config YAML")
    parser.add_argument("--sysprompt", default=PROMPT_PATH, help="Path to system prompt file")
    parser.add_argument("userprompt", help="Text to structure into tasks")

    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    print(f"Arguments: {args}")
    output = structure_notes_to_tasks(
        user_input=args.userprompt, config_path=args.config, prompt_path=args.sysprompt
    )
    print(output.text)