"""Style source presets for voice style transfer."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

STYLE_PRESETS = {
    "UK Grime 1 (Stormzy)": str(PROJECT_ROOT / "voices" / "stormzy_trimmed.mp3"),
    "UK Grime 2 (Skepta)": str(PROJECT_ROOT / "voices" / "skepta_trimmed.mp3"),
    "NY Rap (A$AP Rocky)": str(PROJECT_ROOT / "voices" / "asap_rocky_trimmed.mp3"),
    "Toronto Rap (Drake)": str(PROJECT_ROOT / "voices" / "drake_pushups_trimmed.mp3"),
    "West Coast (Kendrick)": str(PROJECT_ROOT / "voices" / "kendrick_euphoria_trimmed.mp3"),
    "West Coast OG (2Pac)": str(PROJECT_ROOT / "voices" / "2pac_trimmed.mp3"),
    "East Coast OG (Biggie)": str(PROJECT_ROOT / "voices" / "biggie_trimmed.mp3"),
    "Detroit (Eminem)": str(PROJECT_ROOT / "voices" / "eminem_trimmed.mp3"),
    "Wu-Tang (GZA)": str(PROJECT_ROOT / "voices" / "gza_trimmed.mp3"),
    "Chicago (Kanye)": str(PROJECT_ROOT / "voices" / "kanye_trimmed.mp3"),
    "New Orleans (Lil Wayne)": str(PROJECT_ROOT / "voices" / "lil_wayne_trimmed.mp3"),
    "Atlanta Trap (Migos)": str(PROJECT_ROOT / "voices" / "migos_trimmed.mp3"),
}

STYLE_INSTRUCTIONS = {
    "UK Grime 1 (Stormzy)": "aggressive grime rapper, powerful commanding delivery, hard-hitting bars with British accent, intense energy and raw emotion",
    "UK Grime 2 (Skepta)": "sharp grime MC, rapid-fire delivery with London swagger, punchy and precise bars, confident and confrontational energy",
    "NY Rap (A$AP Rocky)": "smooth wavy rapper, laid-back confident delivery, triplet flow with swagger, Harlem cool with melodic undertones",
    "Toronto Rap (Drake)": "smooth melodic rapper, confident and relaxed delivery, slight sing-song flow, emotional range from introspective to boastful",
    "West Coast (Kendrick)": "technical lyrical rapper, dynamic delivery with varied cadence, conscious bars with intensity, switches between smooth and aggressive",
    "West Coast OG (2Pac)": "passionate revolutionary rapper, emotional and intense delivery, poetic storytelling with raw authenticity, switches between aggressive and reflective",
    "East Coast OG (Biggie)": "smooth storyteller with effortless flow, laid-back yet commanding delivery, vivid street narratives with witty punchlines, Brooklyn swagger",
    "Detroit (Eminem)": "rapid-fire technical rapper, intense and aggressive delivery, complex rhyme schemes with emotional intensity, machine-gun flow with precise enunciation",
    "Wu-Tang (GZA)": "cerebral lyricist, precise and methodical delivery, dense wordplay with chess-like strategy, calm intensity with wisdom",
    "Chicago (Kanye)": "soulful confident rapper, melodic and expressive delivery, introspective bars with bravado, innovative flow mixing rap and singing",
    "New Orleans (Lil Wayne)": "metaphor-heavy rapper, eccentric and unpredictable delivery, clever wordplay with Southern drawl, playful yet hard-hitting",
    "Atlanta Trap (Migos)": "triplet flow masters, bouncy and hypnotic delivery, ad-libs and hooks with Atlanta trap energy, catchy and rhythmic",
}

CUSTOM_UPLOAD_LABEL = "Custom Upload..."


def get_dropdown_choices() -> list[str]:
    """Get list of labels for Gradio dropdown."""
    return list(STYLE_PRESETS.keys()) + [CUSTOM_UPLOAD_LABEL]


def get_preset_path(label: str) -> str | None:
    """Get file path for a preset label. Returns None for custom upload."""
    return STYLE_PRESETS.get(label)


def get_style_instructions(label: str) -> str:
    """Get style instructions for a preset label. Returns empty string for custom upload."""
    return STYLE_INSTRUCTIONS.get(label, "")
