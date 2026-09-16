from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = (ROOT / "blueprints/automation/codex_rates/quota_warning.yaml").read_text(
    encoding="utf-8"
)
DOCS = (ROOT / "docs/automations.md").read_text(encoding="utf-8")


def test_blueprint_exposes_its_own_version():
    assert "Codex-LB Rates quota alerts (v2.0.0)" in BLUEPRINT
    assert "Blueprint version: 2.0.0" in BLUEPRINT


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
    assert "Blueprint version: **2.0.0**" in DOCS
    assert "Re-import blueprint" in DOCS
    assert "every 5 minutes" not in DOCS
