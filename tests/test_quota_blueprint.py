import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = (ROOT / "blueprints/automation/codex_rates/quota_warning.yaml").read_text(
    encoding="utf-8"
)
README = (ROOT / "README.md").read_text(encoding="utf-8")
DOCS = (ROOT / "docs/automations.md").read_text(encoding="utf-8")
RELEASES = (ROOT / "docs/releases.md").read_text(encoding="utf-8")
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
HISTORICAL_DESIGN = (
    ROOT / "docs/superpowers/specs/2026-09-10-codex-rates-ha-design.md"
).read_text(encoding="utf-8")


def blueprint_version() -> str:
    match = re.search(r"Blueprint version: (\d+\.\d+\.\d+)", BLUEPRINT)
    assert match is not None, "blueprint description must declare its SemVer"
    return match.group(1)


def test_blueprint_exposes_its_own_version():
    version = blueprint_version()
    assert f"Codex-LB Rates quota alerts (v{version})" in BLUEPRINT


def test_blueprint_version_stays_consistent_across_current_docs():
    version = blueprint_version()
    assert f"Current blueprint: **Codex-LB Rates quota alerts v{version}**" in README
    assert f"Blueprint version: **{version}**" in DOCS
    assert f"Blueprint version: **{version}**" in RELEASES


def test_maintainer_docs_define_independent_blueprint_versioning():
    assert "## Blueprint versioning" in AGENTS
    assert "independent" in AGENTS.lower()
    assert "README.md" in AGENTS
    assert "docs/automations.md" in AGENTS
    assert "tests/test_quota_blueprint.py" in AGENTS
    assert "Integration version" in RELEASES
    assert "Blueprint version" in RELEASES


def test_historical_design_is_marked_as_non_authoritative():
    assert "Historical design snapshot" in HISTORICAL_DESIGN
    assert "source of truth" in HISTORICAL_DESIGN.lower()


def test_blueprint_is_event_driven_without_periodic_polling():
    assert "trigger: time_pattern" not in BLUEPRINT
    assert "entity_id: !input remaining_sensors\n    to: null" in BLUEPRINT


def test_empty_unknown_text_helper_does_not_abort_initial_run():
    assert "states(state_helper) not in ['unknown', 'unavailable']" not in BLUEPRINT
    assert "states.input_text" in BLUEPRINT


def test_alert_memory_uses_compact_stable_tokens():
    assert "sha1" in BLUEPRINT
    assert "[:8]" in BLUEPRINT
    assert "{{ repeat.item }}::low" not in BLUEPRINT
    assert "{{ repeat.item }}::exceeded" not in BLUEPRINT
    assert "{{ repeat.item }}::refreshed" not in BLUEPRINT


def test_mobile_notifications_target_selected_devices_directly():
    assert "action: notify.send_message" in BLUEPRINT
    assert "device_id: !input notify_devices" in BLUEPRINT
    assert "device_attr(" not in BLUEPRINT
    assert '"notify.mobile_app_"' not in BLUEPRINT


def test_docs_explain_blueprint_version_and_reimport_updates():
    assert "Re-import blueprint" in DOCS
    assert "every 5 minutes" not in DOCS
