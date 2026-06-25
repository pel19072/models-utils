# utils/email_templates.py
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_email(template_name: str, **context) -> str:
    """Render an HTML email body from a named template in templates/email/."""
    template = _env.get_template(template_name)
    return template.render(**context)
