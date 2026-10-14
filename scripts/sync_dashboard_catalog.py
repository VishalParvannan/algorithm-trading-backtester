"""Keep visible dashboard controls and its offline catalog snapshot current."""
import json
import re
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.catalog import catalog


def sync():
    definitions = catalog()
    path = ROOT / "web" / "index.html"
    html = path.read_text(encoding="utf-8")
    for name, items in [("source", definitions["sources"]), ("strategy", definitions["strategies"])]:
        options = "".join(f'<option value="{escape(item["id"])}">{escape(item["name"])}</option>' for item in items)
        html = re.sub(rf'(<select name="{name}" id="{name}">).*?(</select>)', lambda match: match[1] + options + match[2], html, flags=re.S)
    snapshot = '<script id="dashboard-catalog" type="application/json">' + json.dumps(definitions, ensure_ascii=True).replace("<", "\\u003c") + '</script>'
    if 'id="dashboard-catalog"' in html:
        html = re.sub(r'<script id="dashboard-catalog" type="application/json">.*?</script>', lambda _: snapshot, html, flags=re.S)
    else:
        html = html.replace('<script src="/app.js"></script>', snapshot + '<script src="/app.js"></script>')
    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    sync()
