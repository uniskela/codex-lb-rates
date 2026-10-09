import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PUBLISHED = [
    ("readme", "README.md", "readme"),
    ("index", "docs/public/index.md", "doc"),
    ("installation", "docs/public/installation.md", "doc"),
    ("configuration", "docs/public/configuration.md", "doc"),
    ("entities", "docs/public/entities.md", "doc"),
    ("dashboard", "docs/public/dashboard.md", "doc"),
    ("automations", "docs/public/automations.md", "doc"),
    ("upgrading", "docs/public/upgrading.md", "doc"),
    ("troubleshooting", "docs/public/troubleshooting.md", "doc"),
    ("releases", "docs/public/releases.md", "doc"),
]


def test_manifest_keeps_published_slugs_on_public_sources():
    manifest = json.loads((ROOT / "docs/manifest.json").read_text(encoding="utf-8"))
    pages = manifest["pages"]
    assert [(page["slug"], page["source"], page["kind"]) for page in pages] == PUBLISHED
    for _slug, source, _kind in PUBLISHED:
        assert (ROOT / source).is_file()
        assert not source.startswith(("docs/internal/", "docs/agents/"))
