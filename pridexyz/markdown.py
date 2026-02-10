from pathlib import Path
from typing import Dict


class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def appy_modrinth_markdown_template(template: str, context: dict) -> str:
    """
    Render a markdown file template by applying string formatting with a context dictionary.
    - Any line containing '!remove_line!' will be removed from the final output.
    - Any Placeholders missing in `context` will be ignored and left as-is.

    Parameters:
        template (Path): The markdown template string with placeholders.
        context (dict): Dictionary of variables to fill into the template.
    """
    rendered = template.format_map(SafeDict({k: v for k, v in context.items()}))

    # Remove lines containing '!remove_line!'
    cleaned = "\n".join(
        line for line in rendered.splitlines() if "!remove_line!" not in line
    )

    return cleaned


def markdown_with_frontmatter_to_dict(path: Path) -> Dict[str, str]:
    """
    Parse a file with YAML-like frontmatter and return a dictionary with
    frontmatter key-values plus a 'body' key for the remaining content.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    data: Dict[str, str] = {}

    if lines and lines[0].strip() == "---":
        # Extract frontmatter
        fm_lines = []
        body_lines = []
        inside_fm = True
        for line in lines[1:]:
            if inside_fm and line.strip() == "---":
                inside_fm = False
                continue
            if inside_fm:
                fm_lines.append(line)
            else:
                body_lines.append(line)

        # Parse key-values from frontmatter
        for line in fm_lines:
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip()

        data["body"] = "\n".join(body_lines).strip()
    else:
        # No frontmatter, everything is body
        data["body"] = text.strip()

    return data
