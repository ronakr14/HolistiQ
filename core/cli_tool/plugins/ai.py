# """
# Plugin: data

# holistiq data scan
# holistiq data migrate
# """

# import os
# import sys
# from types import SimpleNamespace

# from core.cli_tool.registry import registry
# from core.cli_tool.schema import Arg, FieldType
# from apps.structure_note import structure_notes_to_tasks
# from custom_logger.logging_util import get_logger, log_arguments
# from importlib.resources import files

# sys.path.append(os.path.abspath("../apps"))


# logger = get_logger(__name__)


# # ── ai notestructure ───────────────────────────────────────────────────────
# @registry.register_subcommand(
#     group="ai",
#     name="notestructure",
#     help="Structure messy notes to actionable tasks",
#     group_help="AI management commands",
#     args=[
#         Arg("--config", FieldType.STR, help="Path to config file"),
#         Arg("--prompt", FieldType.STR, help="Path to custom prompt file"),
#         Arg("--userinput", FieldType.STR, help="User context"),
#     ],
# )
# def handle_structure_notes_to_tasks(ctx, args: SimpleNamespace) -> None:
#     logger.info(
#         f"Application started for {args['ai_subcommand']} under {args['command']}"
#     )
#     log_arguments(ctx=ctx, args=args)
#     # Determine config and prompt paths, using defaults if not provided
#     config_path = args["config"]
#     if config_path is None:
#         config_path = str(files("holistiq").joinpath("configs/config_llm.yaml"))
#     prompt_path = args["prompt"]
#     if prompt_path is None:
#         prompt_path = str(files("holistiq").joinpath("prompts/notes_structure_tasks_v0.txt"))
#     logger.info("transferring to structure_notes_to_tasks...")
#     ctx.output = structure_notes_to_tasks(
#         args["userinput"], config_path, prompt_path
#     )
#     logger.info("structure_notes_to_tasks action completed")
#     return ctx