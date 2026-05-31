from pathlib import Path
import re


def get_unique_filename(output_dir, base_name):
    """
    Generate unique filename to avoid collisions.

    Example:
    topic.md
    topic_1.md
    topic_2.md
    """
    candidate = output_dir / f"{base_name}.md"

    if not candidate.exists():
        return candidate

    counter = 1
    while True:
        candidate = output_dir / f"{base_name}_{counter}.md"

        if not candidate.exists():
            return candidate

        counter += 1


def split_markdown_by_headers(input_file, output_dir=None):
    """
    Split markdown file into separate files based on H1 headers.
    """

    input_path = Path(input_file)

    if output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    content = input_path.read_text(encoding="utf-8")

    # Split on H1 headers
    sections = re.split(r'(?m)^#\s+', content)

    # Remove empty sections
    sections = [s.strip() for s in sections if s.strip()]

    for section in sections:
        lines = section.splitlines()

        header = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        # Sanitize filename
        base_name = re.sub(r'[^a-zA-Z0-9_\- ]', '', header)
        base_name = base_name.lower().replace(" ", "_")

        # Avoid empty filename edge case
        if not base_name:
            base_name = "untitled"

        # Generate unique file path
        output_file = get_unique_filename(output_dir, base_name)

        # Preserve original markdown structure
        output_content = f"# {header}\n\n{body}\n"

        output_file.write_text(output_content, encoding="utf-8")

        print(f"Created: {output_file}")


# Example usage
split_markdown_by_headers("Tool Summaries.md")


from itertools import product

main = [1, 2]

result = list(product(main, repeat=2))
print(result)