"""Colour paper and brief as HTML and PDF, and the GitHub Pages site in docs/.

Plates and charts are copied at print resolution into docs/img, so the PDFs
stay small and the web page and the print share one set of images.
"""

from __future__ import annotations

import re
import shutil
import subprocess

from PIL import Image

from . import timing
from .paths import CHARTS, MAPS, NOTES, ROOT

PANDOC = "/opt/anaconda3/bin/pandoc"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DOCS = ROOT / "docs"
IMG = DOCS / "img"
PAPER_PDF = DOCS / "paper" / "kano_surface_heat.pdf"
BRIEF_PDF = DOCS / "paper" / "hot_ground_brief.pdf"
PLATE_WIDTH = 2600
CHART_WIDTH = 2200
SCREEN_CSS = """<style>
@media screen {
  body { max-width: 900px; margin: 0 auto; padding: 0 18px 48px; }
  figure img { max-width: 100%; }
}
</style>"""


def images() -> None:
    IMG.mkdir(parents=True, exist_ok=True)
    for src in MAPS.glob("kano_*_plate.png"):
        im = Image.open(src).convert("RGB")
        if im.width > PLATE_WIDTH:
            im = im.resize((PLATE_WIDTH, round(im.height * PLATE_WIDTH / im.width)), Image.LANCZOS)
        im.save(IMG / f"{src.stem}.jpg", quality=88, optimize=True, progressive=True)
    for src in CHARTS.glob("*.png"):
        im = Image.open(src).convert("RGB")
        if im.width > CHART_WIDTH:
            im = im.resize((CHART_WIDTH, round(im.height * CHART_WIDTH / im.width)), Image.LANCZOS)
        im.save(IMG / f"{src.stem}.png", optimize=True)


def _point_at_docs(html: str) -> str:
    html = re.sub(r'src="\.\./maps/([^"/]+)\.png"', r'src="../docs/img/\1.jpg"', html)
    return re.sub(r'src="\.\./charts/([^"/]+)\.png"', r'src="../docs/img/\1.png"', html)


def render(md: str, template: str) -> str:
    out = NOTES / md.replace(".md", ".html")
    subprocess.check_call([PANDOC, str(NOTES / md), "-o", str(out), "--standalone", f"--template={NOTES / template}"])
    out.write_text(_point_at_docs(out.read_text(encoding="utf-8")), encoding="utf-8")
    return str(out)


def pdf(html: str, dest) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.check_call([CHROME, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
                           "--no-pdf-header-footer", "--virtual-time-budget=120000", f"--print-to-pdf={dest}", html],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest.stat().st_size


def site(brief_html: str) -> None:
    html = open(brief_html, encoding="utf-8").read().replace("../docs/img/", "img/")
    html = html.replace("</head>", f"{SCREEN_CSS}\n</head>", 1)
    html = html.replace(
        'Code and data</a>',
        'Code and data</a> · <a href="paper/hot_ground_brief.pdf">This brief (PDF)</a>', 1)
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    shutil.copy2(NOTES / "print.css", DOCS / "print.css")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    t0 = timing.start("paper and brief", "pandoc, Chrome PDF, docs/ site")
    images()
    paper_html = render("results.md", "template.html")
    brief_html = render("brief.md", "brief-template.html")
    a = pdf(paper_html, PAPER_PDF)
    b = pdf(brief_html, BRIEF_PDF)
    site(brief_html)
    timing.done("paper and brief", t0, f"paper {a / 1e6:.1f} MB, brief {b / 1e6:.1f} MB → docs/")


if __name__ == "__main__":
    main()
