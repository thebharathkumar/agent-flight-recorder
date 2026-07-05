"""Plugin and marketplace manifests parse and carry the required fields."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_plugin_manifest():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "flight-recorder"
    assert manifest["version"]
    assert manifest["license"] == "MIT"
    assert "thebharathkumar/agent-flight-recorder" in manifest["repository"]


def test_marketplace_manifest():
    manifest = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert manifest["name"] == "agent-flight-recorder"
    assert manifest["owner"]["name"]
    entry = manifest["plugins"][0]
    assert entry["name"] == "flight-recorder"
    assert entry["source"] == "./"


def test_license_is_mit():
    text = (ROOT / "LICENSE").read_text()
    assert "MIT License" in text
    assert "Bharath Kumar" in text
