"""Re-stamp every /static/*.css|js reference in the HTML pages with a content hash (?v=<sha256[:8]>).

Run this after editing any CSS or JS file so the browser is forced to fetch the new version instead of
serving its cached copy. tests/test_insights.py::test_asset_version_stamps_match_the_files_on_disk fails
until this has been run.
"""
import hashlib
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"

PATTERN = re.compile(r'(src|href)="(/static/[^"?]+\.(?:js|css))(?:\?v=[0-9a-f]+)?"')


def stamp_one(page: Path) -> int:
    text = page.read_text(encoding="utf-8")

    def repl(m: re.Match) -> str:
        attr, url_path = m.group(1), m.group(2)
        asset = STATIC / url_path[len("/static/"):]
        if not asset.exists():
            return m.group(0)
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()[:8]
        return f'{attr}="{url_path}?v={digest}"'

    new_text, count = PATTERN.subn(repl, text)
    if new_text != text:
        page.write_text(new_text, encoding="utf-8")
    return count


def main() -> None:
    total = 0
    for page in sorted(STATIC.glob("*.html")):
        n = stamp_one(page)
        print(f"{page.name}: {n} asset reference(s) stamped")
        total += n
    print(f"done ({total} references across all pages)")


if __name__ == "__main__":
    main()
