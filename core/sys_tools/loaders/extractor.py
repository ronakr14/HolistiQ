import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_sql_queries(file_path: Path, encoding: str = "utf-8") -> list[str]:
    """
    Extracts SQL queries from a given file path.

    This function reads the file content, removes SQL comments, splits the content by semicolon,
    and cleans the queries by stripping and filtering out empty or comment-only queries.

    Args:
        file_path (Path): The path to the file to extract queries from.
        encoding (str): The encoding to use when reading the file. Defaults to 'utf-8'.

    Returns:
        list[str]: A list of extracted SQL queries.
    """

    try:
        content = file_path.read_text(encoding=encoding)  # type: ignore
    except UnicodeDecodeError:
        # Fallback to latin-1 encoding
        content = file_path.read_text(encoding="latin-1")
        logger.warning(f"Used latin-1 encoding for {file_path}")

    # Remove SQL comments
    content = _remove_sql_comments(content)

    # Split by semicolon but handle quoted strings
    queries = _smart_split_queries(content)

    # Clean and filter queries
    cleaned_queries = []
    for query in queries:
        query = query.strip()
        if query and not _is_comment_only(query):
            cleaned_queries.append(query)

    logger.debug(f"Extracted {len(cleaned_queries)} queries from {file_path.name}")
    return cleaned_queries


def _remove_sql_comments(content: str) -> str:
    # Remove single-line comments (-- comment)
    """
    Removes SQL comments from a given content string.

    This function uses regular expressions to remove single-line comments (starting with "--")
    and multi-line comments (/* comment */).

    Args:
        content (str): The content string to remove SQL comments from.

    Returns:
        str: The content string with SQL comments removed.
    """
    content = re.sub(r"--.*?$", "", content, flags=re.MULTILINE)

    # Remove multi-line comments (/* comment */)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)

    return content


def _smart_split_queries(content: str) -> list[str]:
    """
    Splits a given content string into individual SQL queries while handling quoted strings.

    This function iterates through the content string, tracking whether it is currently inside a single-quoted or double-quoted string.
    When it encounters a semicolon outside of a quoted string, it adds the current query to the result list and resets the current query.
    Finally, it adds the last query to the result list if it doesn't end with a semicolon.

    Args:
        content (str): The content string to split into individual SQL queries.

    Returns:
        list[str]: A list of individual SQL queries extracted from the content string.
    """
    queries = []
    current_query = ""
    in_single_quote = False
    in_double_quote = False

    i = 0
    while i < len(content):
        char = content[i]

        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif char == ";" and not in_single_quote and not in_double_quote:
            if current_query.strip():
                queries.append(current_query.strip())
            current_query = ""
            i += 1
            continue

        current_query += char
        i += 1

    # Add the last query if it doesn't end with semicolon
    if current_query.strip():
        queries.append(current_query.strip())

    return queries


def _is_comment_only(query: str) -> bool:
    # Remove all whitespace and check if anything substantial remains
    """
    Checks if a given query string is empty or only contains a SQL comment.

    This function removes all whitespace from the query string and checks if the resulting string is empty or starts with a SQL comment marker ("--" or "/*").

    Args:
        query (str): The query string to check.

    Returns:
        bool: True if the query string is empty or only contains a SQL comment, False otherwise.
    """
    cleaned = re.sub(r"\s+", "", query)
    return not cleaned or cleaned.startswith("--") or cleaned.startswith("/*")
