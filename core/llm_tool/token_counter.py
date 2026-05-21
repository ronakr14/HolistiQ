from custom_logger.logging_util import get_logger

logger = get_logger(__name__)


def count_tokens(text: str, model: str, mode: str) -> int:
    logger.debug(f"counting tokens using {mode} mode.")
    if mode == "transformer":
        return _count_tokens_transformers(text, model)
    return _count_tokens_tiktoken(text, model)


def _count_tokens_tiktoken(text: str, model: str) -> int:
    try:
        import tiktoken
    except ImportError as e:
        raise RuntimeError(
            "tiktoken is not installed. Please install it with `pip install tiktoken`"
        ) from e
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))


def _count_tokens_transformers(text: str, model: str) -> int:
    try:
        from transformers import AutoTokenizer
    except ImportError as e:
        raise RuntimeError(
            "transformers is not installed. Please install it with `pip install transformers`"
        ) from e
    if "qwen" in model:
        model = f"qwen/{model.replace(':', '-').split('-q4')[0]}"

    tokenizer = AutoTokenizer.from_pretrained(model)

    tokens = tokenizer.encode(text)
    return len(tokens)
