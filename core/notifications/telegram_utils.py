"""
telegram_utils.py
A small framework on top of python-telegram-bot (v20+) to register commands and
send messages / solicit feedback from users.

Design goals:
- Register commands via @register_command (supports sync + async handlers)
- Support sending messages programmatically
- Provide "ask_feedback" helper that sends inline buttons mapped to registered commands
- Lightweight context passed to handlers so you can extend it
"""

import asyncio
from typing import Any, Awaitable, Callable, Optional, Union

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from libs.mixers.logger_mixin import get_logger

HandlerFunc = Callable[
    [Update, ContextTypes.DEFAULT_TYPE, dict[str, Any]], Union[Awaitable, None]
]

logger = get_logger("Telegram", component="Utils")


class CommandRegistry:
    """
    Keeps mapping from command name -> handler function and metadata.
    Handlers are expected to accept (update, context, meta).
    meta is a dict allowing arbitrary extra info (like name, description).
    """

    def __init__(self):
        self._handlers: dict[str, dict[str, Any]] = {}

    def register(self, name: str, description: str = "", replace: bool = False):
        """
        Decorator to register a handler.
        Usage:
            @registry.register("approve", "Approve the request")
            async def handle_approve(update, context, meta): ...
        """

        def decorator(func: HandlerFunc):
            if name in self._handlers and not replace:
                raise RuntimeError(f"Command {name!r} already registered")
            self._handlers[name] = {"fn": func, "description": description}
            logger.info(f"Registered command {name} -> {func.__name__}")
            return func

        return decorator

    def get(self, name: str):
        return self._handlers.get(name)

    def all_commands(self):
        return {name: info["description"] for name, info in self._handlers.items()}


class TelegramController:
    """
    High-level controller around a telegram bot application.
    Use start() to run (polling) or provide application to run as webhook externally.
    """

    def __init__(self, token: str, default_meta: Optional[dict[str, Any]] = None):
        self.token = token
        self.registry = CommandRegistry()
        self.application = (
            ApplicationBuilder().token(token).concurrent_updates(True).build()
        )
        self.default_meta = default_meta or {}

        # wire built-in handlers
        self.application.add_handler(CallbackQueryHandler(self._on_callback_query))
        # optional: simple fallback message handler
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_text_message)
        )

    async def _on_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Callback query handler for inline button presses.
        The callback_data we set is "cmd:<command_name>"
        """
        query = update.callback_query
        if not query or not query.data:
            return
        data = query.data
        if not data.startswith("cmd:"):
            # ignore
            await query.answer()
            return
        cmd = data.split(":", 1)[1]
        await query.answer()  # removes "loading" state
        await self._dispatch_command(cmd, update, context)

    async def _on_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Basic fallback: if user types a registered command name as a text message (not /slash),
        dispatch that command. This is optional behavior to support free-text feedback.
        """
        text = (update.message.text or "").strip()
        if not text:
            return
        # If user typed exact registered command name, dispatch
        if text in self.registry._handlers:
            await self._dispatch_command(text, update, context)

    async def _dispatch_command(
        self, cmd: str, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        entry = self.registry.get(cmd)
        if not entry:
            # optional: send a reply that command unknown
            if update.effective_message:
                await update.effective_message.reply_text(f"Unknown command: {cmd}")
            return
        fn = entry["fn"]
        meta = {"command": cmd, "description": entry.get("description", "")}
        meta.update(self.default_meta)
        try:
            res = fn(update, context, meta)
            if asyncio.iscoroutine(res):
                await res
        except Exception as exc:
            logger.exception("Error handling command %s", cmd)
            if update.effective_message:
                await update.effective_message.reply_text(
                    f"Handler for {cmd} failed: {exc}"
                )

    def register_command(self, name: str, description: str = "", replace: bool = False):
        """Proxy to registry.register"""
        return self.registry.register(name, description, replace=replace)

    async def send_message(
        self, chat_id: int, text: str, reply_markup=None, parse_mode=None
    ):
        bot = Bot(self.token)
        return await bot.send_message(
            chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode
        )

    async def ask_feedback(
        self,
        chat_id: int,
        text: str,
        command_list: list[str],
        title_map: Optional[dict[str, str]] = None,
    ):
        """
        Sends a message with inline buttons — each button triggers a registered command.
        `command_list` are the command names to present.
        `title_map` optionally maps command -> button label.
        Returns the sent Message object.
        """
        title_map = title_map or {}
        keyboard = [
            [InlineKeyboardButton(title_map.get(cmd, cmd), callback_data=f"cmd:{cmd}")]
            for cmd in command_list
        ]
        markup = InlineKeyboardMarkup(keyboard)
        return await self.send_message(chat_id, text, reply_markup=markup)

    def add_command_handler(self, telegram_command: str, description: str = ""):
        """
        Add a standard /command handler to the Telegram bot. When the user uses /command,
        we'll trigger the registered handler in our registry. This is helpful so users can
        use both inline buttons or classic slash commands.
        Call after registering functions.
        """

        async def _handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            # remove leading slash if any
            cmd_name = telegram_command.lstrip("/").split()[0]
            await self._dispatch_command(cmd_name, update, context)

        self.application.add_handler(
            CommandHandler(telegram_command.lstrip("/"), _handler)
        )
        logger.info(
            "Added telegram CommandHandler for /%s", telegram_command.lstrip("/")
        )

    def run_polling(self):
        """Start the bot via polling (blocking)."""
        logger.info("Starting polling")
        self.application.run_polling()

    async def start(self):
        """Start the application (for non-blocking control)."""
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()

    async def stop(self):
        await self.application.updater.stop_polling()
        await self.application.stop()
        await self.application.shutdown()
