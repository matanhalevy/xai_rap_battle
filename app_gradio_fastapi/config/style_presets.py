"""Style source presets for voice style transfer."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

STYLE_PRESETS = {
    "UK Grime 1 (Stormzy)": str(PROJECT_ROOT / "voices" / "stormzy_trimmed.mp3"),
    "NY Rap (A$AP Rocky)": str(PROJECT_ROOT / "voices" / "asap_rocky_trimmed.mp3"),
    "Toronto Rap (Drake)": str(PROJECT_ROOT / "voices" / "drake_pushups_trimmed.mp3"),
    "West Coast (Kendrick)": str(PROJECT_ROOT / "voices" / "kendrick_euphoria_trimmed.mp3"),
    # Add more presets here
}

CUSTOM_UPLOAD_LABEL = "Custom Upload..."


def get_dropdown_choices() -> list[str]:
    """Get list of labels for Gradio dropdown."""
    return list(STYLE_PRESETS.keys()) + [CUSTOM_UPLOAD_LABEL]


def get_preset_path(label: str) -> str | None:
    """Get file path for a preset label. Returns None for custom upload."""
    return STYLE_PRESETS.get(label)
