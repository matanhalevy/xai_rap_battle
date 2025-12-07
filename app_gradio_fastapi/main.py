import gradio as gr
from fastapi import FastAPI
from functools import partial

from app_gradio_fastapi import routes
from app_gradio_fastapi.helpers.formatters import request_formatter
from app_gradio_fastapi.helpers.session_logger import change_logging
from app_gradio_fastapi.services.voice_api import generate_rap_voice
from app_gradio_fastapi.services.elevenlabs_api import create_style_reference
from app_gradio_fastapi.services.beat_api import generate_beat_pattern
from app_gradio_fastapi.services.beat_generator import get_generator
from app_gradio_fastapi.services.lyric_api import generate_all_verses
from app_gradio_fastapi.services.storyboard_pipeline import run_storyboard_pipeline, run_storyboard_only
from app_gradio_fastapi.config.style_presets import (
    get_dropdown_choices,
    get_preset_path,
    get_style_instructions,
    CUSTOM_UPLOAD_LABEL,
)



change_logging()

CUSTOM_GRADIO_PATH = "/"
app = FastAPI(title="Grok DJ Rap Battle", version="1.0")
app.include_router(routes.router)


def handle_rap_generation(lyrics: str, style: str, voice_file: str | None):
    """Handle rap voice generation from Gradio UI."""
    audio_path, status = generate_rap_voice(
        lyrics=lyrics,
        style_instructions=style if style.strip() else "aggressive hip-hop rapper with rhythmic flow",
        voice_file=voice_file,
    )
    return audio_path, status


# Store style references for both characters
_style_reference_cache = {
    "char1": {"path": None, "voice_id": None},
    "char2": {"path": None, "voice_id": None},
}


def resolve_style_source(dropdown_value: str, custom_file) -> str | None:
    """Resolve style source from dropdown preset or custom upload."""
    preset_path = get_preset_path(dropdown_value)
    if preset_path:
        return preset_path
    if custom_file is not None:
        return custom_file.name if hasattr(custom_file, "name") else custom_file
    return None


def update_custom_visibility(selection: str):
    """Show custom upload only when 'Custom Upload...' is selected."""
    return gr.update(visible=(selection == CUSTOM_UPLOAD_LABEL))


def update_style_dropdown(selection: str):
    """Update custom visibility and auto-populate style instructions."""
    visibility = gr.update(visible=(selection == CUSTOM_UPLOAD_LABEL))
    instructions = get_style_instructions(selection)
    return visibility, instructions


def handle_create_style_reference(
    character: str,
    voice_identity_file,
    style_dropdown: str,
    custom_style_file,
    reference_name: str,
    celebrity_mode: bool,
    stability: float,
    similarity_boost: float,
):
    """Stage 1: Create voice+style reference for a specific character."""
    if voice_identity_file is None:
        return None, f"Error: Please upload a voice identity file for {character}"

    # Resolve style source from dropdown or custom upload
    style_path = resolve_style_source(style_dropdown, custom_style_file)
    if not style_path:
        return None, "Error: Please select a style preset or upload a custom style file"

    # Get file path from Gradio file object
    voice_path = voice_identity_file.name if hasattr(voice_identity_file, "name") else voice_identity_file
    name = reference_name.strip() if reference_name.strip() else character

    output_path, voice_id, status = create_style_reference(
        voice_identity_file=voice_path,
        style_source_file=style_path,
        reference_name=name,
        celebrity_mode=celebrity_mode,
        stability=stability,
        similarity_boost=similarity_boost,
    )

    # Cache for Stage 2
    if output_path:
        _style_reference_cache[character]["path"] = output_path
        _style_reference_cache[character]["voice_id"] = voice_id

    return output_path, status


# Create partial handlers for each character
handle_create_ref_char1 = partial(handle_create_style_reference, "char1")
handle_create_ref_char2 = partial(handle_create_style_reference, "char2")


def handle_generate_with_style(character: str, lyrics: str, style_instructions: str):
    """Stage 2: Generate new lyrics using the style reference for a specific character."""
    if not lyrics.strip():
        return None, f"Error: Please enter rap lyrics for {character}"

    ref_path = _style_reference_cache[character]["path"]
    if not ref_path:
        return None, f"Error: Please create a style reference for {character} first (Stage 1)"

    # Use xAI TTS with the style reference as voice sample
    audio_path, status = generate_rap_voice(
        lyrics=lyrics,
        style_instructions=style_instructions if style_instructions.strip() else "aggressive rapper with rhythmic flow",
        voice_file=ref_path,
    )
    return audio_path, status


# Create partial handlers for each character
handle_generate_char1 = partial(handle_generate_with_style, "char1")
handle_generate_char2 = partial(handle_generate_with_style, "char2")


# Store generated verses for audio generation
_verses_cache = {
    "verse1": "",
    "verse2": "",
    "verse3": "",
    "verse4": "",
}

# Store generated audio paths for combining
_audio_cache = {
    "verse1": None,
    "verse2": None,
    "verse3": None,
    "verse4": None,
}


def handle_generate_all_lyrics(
    char1_name: str,
    char1_twitter: str,
    char2_name: str,
    char2_twitter: str,
    theme: str,
    scene: str,
):
    """Generate all 4 verses using Grok AI."""
    if not char1_name.strip():
        return "", "", "", "", "Error: Please enter Character 1's name"
    if not char2_name.strip():
        return "", "", "", "", "Error: Please enter Character 2's name"
    if not theme.strip():
        return "", "", "", "", "Error: Please enter a battle theme"

    verses, status = generate_all_verses(
        char1_name=char1_name.strip(),
        char1_twitter=char1_twitter.strip() if char1_twitter else None,
        char2_name=char2_name.strip(),
        char2_twitter=char2_twitter.strip() if char2_twitter else None,
        topic=theme.strip(),
        description="",
        scene_description=scene.strip() if scene else "",
    )

    # Pad verses if fewer than 4 were generated
    while len(verses) < 4:
        verses.append("")

    # Cache verses for audio generation
    for i, verse in enumerate(verses[:4], 1):
        _verses_cache[f"verse{i}"] = verse

    return verses[0], verses[1], verses[2], verses[3], status


def handle_generate_all_audio(
    custom_verse1: str,
    custom_verse2: str,
    custom_verse3: str,
    custom_verse4: str,
    grok_verse1: str,
    grok_verse2: str,
    grok_verse3: str,
    grok_verse4: str,
    char1_style: str,
    char2_style: str,
):
    """Generate audio for all 4 verses and combine them using ffmpeg."""
    import subprocess
    import tempfile
    import os

    custom_verses = [custom_verse1, custom_verse2, custom_verse3, custom_verse4]
    grok_verses = [grok_verse1, grok_verse2, grok_verse3, grok_verse4]
    styles = [char1_style, char2_style, char1_style, char2_style]
    characters = ["char1", "char2", "char1", "char2"]

    audio_paths = []
    errors = []

    # Generate each verse
    for i in range(4):
        verse_num = i + 1
        custom = custom_verses[i]
        grok = grok_verses[i]
        style = styles[i]
        character = characters[i]

        # Use custom verse if provided, otherwise use Grok-generated
        lyrics = custom.strip() if custom.strip() else grok.strip()

        if not lyrics:
            errors.append(f"Verse {verse_num}: No lyrics")
            audio_paths.append(None)
            continue

        ref_path = _style_reference_cache[character]["path"]
        if not ref_path:
            errors.append(f"Verse {verse_num}: No voice reference for {character}")
            audio_paths.append(None)
            continue

        audio_path, status = generate_rap_voice(
            lyrics=lyrics,
            style_instructions=style if style.strip() else "aggressive rapper with rhythmic flow",
            voice_file=ref_path,
        )

        if audio_path:
            _audio_cache[f"verse{verse_num}"] = audio_path
            audio_paths.append(audio_path)
        else:
            errors.append(f"Verse {verse_num}: {status}")
            audio_paths.append(None)

    # Check if we have all audio files
    if None in audio_paths:
        error_msg = "; ".join(errors) if errors else "Some verses failed to generate"
        return (
            audio_paths[0],
            audio_paths[1],
            audio_paths[2],
            audio_paths[3],
            None,
            f"Partial generation: {error_msg}",
        )

    # Combine all audio files using ffmpeg
    try:
        # Create a temporary file list for ffmpeg concat
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            list_file = f.name
            for path in audio_paths:
                f.write(f"file '{path}'\n")

        # Output combined file
        combined_path = tempfile.mktemp(suffix=".mp3")

        # Use ffmpeg to concatenate
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", combined_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        # Clean up list file
        os.unlink(list_file)

        if result.returncode != 0:
            return (
                audio_paths[0],
                audio_paths[1],
                audio_paths[2],
                audio_paths[3],
                None,
                f"FFmpeg error: {result.stderr}",
            )

        return (
            audio_paths[0],
            audio_paths[1],
            audio_paths[2],
            audio_paths[3],
            combined_path,
            "All audio generated successfully!",
        )

    except Exception as e:
        return (
            audio_paths[0],
            audio_paths[1],
            audio_paths[2],
            audio_paths[3],
            None,
            f"Error combining: {e}",
        )


def handle_beat_generation(style: str, bpm: int, bars: int, loops: int):
    """Handle beat generation from Gradio UI."""
    # Step 1: Get beat pattern JSON from Grok
    json_str, status = generate_beat_pattern(style=style, bpm=bpm, bars=bars)
    if json_str is None:
        return None, None, status

    # Step 2: Synthesize audio from the pattern
    try:
        generator = get_generator()
        audio_path, pattern = generator.generate_from_json(json_str, loops=loops)
        return audio_path, json_str, f"Generated: {pattern.metadata.title} ({pattern.metadata.bpm} BPM)"
    except Exception as e:
        return None, json_str, f"Synthesis error: {e}"


def handle_storyboard_preview(script: str, theme: str, char_a: str, char_b: str):
    """Generate storyboard images only (quick preview)."""
    if not script.strip():
        return [], "Error: Please enter a rap script"
    if not theme.strip():
        return [], "Error: Please enter a theme"

    images, messages = run_storyboard_only(
        script=script,
        theme=theme,
        character_a_desc=char_a if char_a.strip() else "intense male rapper in streetwear",
        character_b_desc=char_b if char_b.strip() else "confident female rapper in urban fashion",
    )
    return images, "\n".join(messages)


def handle_full_video_generation(
    script: str,
    theme: str,
    speaker_a: str,
    speaker_b: str,
    speaker_a_img,
    speaker_b_img,
    test_mode: bool,
    audio_turn1,
    audio_turn2,
    audio_turn3,
    audio_turn4,
    beat_file,
    char_a: str,
    char_b: str,
):
    """Generate rap battle video with audio clips + beat + lip sync."""
    if not script.strip():
        return [], None, "Error: Please enter a rap script"
    if not theme.strip():
        return [], None, "Error: Please enter a theme"

    # Collect audio paths for each turn
    audio_files = [audio_turn1, audio_turn2] if test_mode else [audio_turn1, audio_turn2, audio_turn3, audio_turn4]
    audio_paths = []
    for i, audio_file in enumerate(audio_files, 1):
        if audio_file is None:
            return [], None, f"Error: Please upload audio for Turn {i}"
        path = audio_file.name if hasattr(audio_file, "name") else audio_file
        audio_paths.append(path)

    # Beat track (optional)
    beat_path = None
    if beat_file is not None:
        beat_path = beat_file.name if hasattr(beat_file, "name") else beat_file

    result = run_storyboard_pipeline(
        script=script,
        theme=theme,
        audio_clips=audio_paths,
        beat_path=beat_path,
        speaker_a_name=speaker_a.strip(),
        speaker_b_name=speaker_b.strip(),
        character_a_desc=char_a if char_a.strip() else "intense male rapper in streetwear",
        character_b_desc=char_b if char_b.strip() else "confident female rapper in urban fashion",
        test_mode=test_mode,
        enable_lipsync=True,  # Always enabled
    )

    return result.storyboard_images, result.final_video, "\n".join(result.status_messages)


with gr.Blocks(title="Grok DJ Rap Battle") as demo:
    gr.Markdown("# Grok DJ Rap Battle")

    with gr.Tabs():
        with gr.TabItem("Rap Voice Test"):
            gr.Markdown("Test Grok Voice API for rap delivery and voice cloning.")

            with gr.Row():
                with gr.Column():
                    lyrics_input = gr.Textbox(
                        lines=8,
                        placeholder="Enter your rap lyrics here...\n\nExample:\nYo, I'm the AI on the mic tonight,\nSpitting fire bars, yeah I do it right,\nGrok voice flowing with the beat so tight,\nRap battle champion, I own this fight!",
                        label="Rap Lyrics",
                    )
                    style_input = gr.Textbox(
                        lines=2,
                        placeholder="e.g., aggressive hip-hop rapper, old school 90s flow, fast energetic delivery",
                        label="Style Instructions",
                        value="aggressive hip-hop rapper with rhythmic flow",
                    )
                    voice_upload = gr.File(
                        label="Voice Sample (optional, for cloning)",
                        file_types=[".mp3", ".m4a", ".wav"],
                    )
                    generate_btn = gr.Button("Generate Rap", variant="primary")

                with gr.Column():
                    audio_output = gr.Audio(label="Generated Audio", type="filepath")
                    status_output = gr.Textbox(label="Status", interactive=False)

            generate_btn.click(
                fn=handle_rap_generation,
                inputs=[lyrics_input, style_input, voice_upload],
                outputs=[audio_output, status_output],
            )

        with gr.TabItem("Rap Battle Audio"):
            gr.Markdown("""## Rap Battle Audio
Configure your rap battle characters and generate verses with audio.
            """)

            gr.Markdown("### Battle Setup")
            with gr.Row():
                battle_theme = gr.Textbox(
                    label="Battle Theme",
                    placeholder="e.g., Tech CEOs, AI vs Humans, East Coast vs West Coast",
                )
            with gr.Row():
                scene_description = gr.Textbox(
                    label="Scene Description",
                    lines=2,
                    placeholder="Describe the setting (used for lyrics context and future video generation)...",
                )
            gr.Markdown("---")

            gr.Markdown("### Stage 1: Create Voice + Style References")
            with gr.Row():
                # Character 1
                with gr.Column():
                    gr.Markdown("#### Character 1")
                    char1_name = gr.Textbox(
                        label="Character Name",
                        placeholder="e.g., Elon Musk",
                    )
                    char1_twitter = gr.Textbox(
                        label="Twitter Handle (optional)",
                        placeholder="e.g., @elonmusk",
                    )
                    char1_voice_identity = gr.File(
                        label="Voice Identity (who to sound like)",
                        file_types=[".mp3", ".m4a", ".wav"],
                    )
                    char1_style_dropdown = gr.Dropdown(
                        choices=get_dropdown_choices(),
                        value=get_dropdown_choices()[0],
                        label="Style Source",
                    )
                    char1_custom_style = gr.File(
                        label="Custom Style File",
                        file_types=[".mp3", ".m4a", ".wav"],
                        visible=False,
                    )
                    char1_reference_name = gr.Textbox(
                        label="Reference Name",
                        value="character_1",
                        placeholder="e.g., Elon Rapper",
                    )
                    char1_celebrity_mode = gr.Checkbox(
                        label="Celebrity Voice Mode",
                        value=False,
                        info="Enable if ElevenLabs blocks the voice.",
                    )
                    with gr.Accordion("Voice Settings", open=False):
                        char1_similarity = gr.Slider(
                            minimum=0.0, maximum=1.0, value=0.85, step=0.05,
                            label="Similarity Boost",
                            info="Higher = more like voice identity.",
                        )
                        char1_stability = gr.Slider(
                            minimum=0.0, maximum=1.0, value=0.5, step=0.05,
                            label="Stability",
                            info="Higher = more consistent voice.",
                        )
                    char1_create_btn = gr.Button("Create Reference 1", variant="primary")
                    char1_ref_audio = gr.Audio(label="Reference Output", type="filepath")
                    char1_ref_status = gr.Textbox(label="Status", interactive=False)

                # Character 2
                with gr.Column():
                    gr.Markdown("#### Character 2")
                    char2_name = gr.Textbox(
                        label="Character Name",
                        placeholder="e.g., Mark Zuckerberg",
                    )
                    char2_twitter = gr.Textbox(
                        label="Twitter Handle (optional)",
                        placeholder="e.g., @zaborevsky",
                    )
                    char2_voice_identity = gr.File(
                        label="Voice Identity (who to sound like)",
                        file_types=[".mp3", ".m4a", ".wav"],
                    )
                    char2_style_dropdown = gr.Dropdown(
                        choices=get_dropdown_choices(),
                        value=get_dropdown_choices()[0],
                        label="Style Source",
                    )
                    char2_custom_style = gr.File(
                        label="Custom Style File",
                        file_types=[".mp3", ".m4a", ".wav"],
                        visible=False,
                    )
                    char2_reference_name = gr.Textbox(
                        label="Reference Name",
                        value="character_2",
                        placeholder="e.g., Zuck Rapper",
                    )
                    char2_celebrity_mode = gr.Checkbox(
                        label="Celebrity Voice Mode",
                        value=False,
                        info="Enable if ElevenLabs blocks the voice.",
                    )
                    with gr.Accordion("Voice Settings", open=False):
                        char2_similarity = gr.Slider(
                            minimum=0.0, maximum=1.0, value=0.85, step=0.05,
                            label="Similarity Boost",
                            info="Higher = more like voice identity.",
                        )
                        char2_stability = gr.Slider(
                            minimum=0.0, maximum=1.0, value=0.5, step=0.05,
                            label="Stability",
                            info="Higher = more consistent voice.",
                        )
                    char2_create_btn = gr.Button("Create Reference 2", variant="primary")
                    char2_ref_audio = gr.Audio(label="Reference Output", type="filepath")
                    char2_ref_status = gr.Textbox(label="Status", interactive=False)

            # Stage 1 buttons
            char1_create_btn.click(
                fn=handle_create_ref_char1,
                inputs=[
                    char1_voice_identity,
                    char1_style_dropdown,
                    char1_custom_style,
                    char1_reference_name,
                    char1_celebrity_mode,
                    char1_stability,
                    char1_similarity,
                ],
                outputs=[char1_ref_audio, char1_ref_status],
            )
            char2_create_btn.click(
                fn=handle_create_ref_char2,
                inputs=[
                    char2_voice_identity,
                    char2_style_dropdown,
                    char2_custom_style,
                    char2_reference_name,
                    char2_celebrity_mode,
                    char2_stability,
                    char2_similarity,
                ],
                outputs=[char2_ref_audio, char2_ref_status],
            )

            gr.Markdown("---")
            gr.Markdown("### Stage 2: Generate Lyrics & Audio")

            # Style instructions for both characters (shared across tabs)
            with gr.Row():
                with gr.Column():
                    char1_style_instructions = gr.Textbox(
                        lines=2,
                        placeholder="e.g., aggressive rapper with rhythmic flow",
                        label="Character 1 Style Instructions",
                        value="",
                    )
                with gr.Column():
                    char2_style_instructions = gr.Textbox(
                        lines=2,
                        placeholder="e.g., confident rapper with smooth delivery",
                        label="Character 2 Style Instructions",
                        value="",
                    )

            with gr.Tabs():
                with gr.TabItem("Grok Generated"):
                    gr.Markdown("Generate all 4 verses automatically using Grok AI.")
                    with gr.Row():
                        generate_lyrics_btn = gr.Button(
                            "Generate All Lyrics",
                            variant="primary",
                            scale=2,
                        )
                        lyrics_status = gr.Textbox(
                            label="Generation Status",
                            interactive=False,
                            scale=3,
                        )
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("##### Verse 1 (Character 1)")
                            grok_verse1 = gr.Textbox(
                                lines=6,
                                label="Generated Verse 1",
                                interactive=False,
                            )
                        with gr.Column():
                            gr.Markdown("##### Verse 2 (Character 2)")
                            grok_verse2 = gr.Textbox(
                                lines=6,
                                label="Generated Verse 2",
                                interactive=False,
                            )
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("##### Verse 3 (Character 1)")
                            grok_verse3 = gr.Textbox(
                                lines=6,
                                label="Generated Verse 3",
                                interactive=False,
                            )
                        with gr.Column():
                            gr.Markdown("##### Verse 4 (Character 2)")
                            grok_verse4 = gr.Textbox(
                                lines=6,
                                label="Generated Verse 4",
                                interactive=False,
                            )

                with gr.TabItem("Custom Lyrics"):
                    gr.Markdown("Enter your own lyrics for each verse.")
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("##### Verse 1 (Character 1)")
                            custom_verse1 = gr.Textbox(
                                lines=6,
                                placeholder="Enter opening verse for Character 1...",
                                label="Verse 1",
                            )
                        with gr.Column():
                            gr.Markdown("##### Verse 2 (Character 2)")
                            custom_verse2 = gr.Textbox(
                                lines=6,
                                placeholder="Enter response verse for Character 2...",
                                label="Verse 2",
                            )
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("##### Verse 3 (Character 1)")
                            custom_verse3 = gr.Textbox(
                                lines=6,
                                placeholder="Enter comeback verse for Character 1...",
                                label="Verse 3",
                            )
                        with gr.Column():
                            gr.Markdown("##### Verse 4 (Character 2)")
                            custom_verse4 = gr.Textbox(
                                lines=6,
                                placeholder="Enter closing verse for Character 2...",
                                label="Verse 4",
                            )

            gr.Markdown("---")
            gr.Markdown("### Stage 3: Audio Output")
            with gr.Row():
                generate_all_audio_btn = gr.Button(
                    "Generate All Audio",
                    variant="primary",
                    scale=2,
                )
                audio_status = gr.Textbox(
                    label="Status",
                    interactive=False,
                    scale=3,
                )

            gr.Markdown("##### Individual Verses")
            with gr.Row():
                verse1_audio = gr.Audio(label="Verse 1 (Character 1)", type="filepath")
                verse2_audio = gr.Audio(label="Verse 2 (Character 2)", type="filepath")
            with gr.Row():
                verse3_audio = gr.Audio(label="Verse 3 (Character 1)", type="filepath")
                verse4_audio = gr.Audio(label="Verse 4 (Character 2)", type="filepath")

            gr.Markdown("##### Combined Battle")
            combined_audio = gr.Audio(label="Full Battle (All 4 Verses)", type="filepath")

            # Dropdown change handlers (auto-populate style instructions)
            char1_style_dropdown.change(
                fn=update_style_dropdown,
                inputs=[char1_style_dropdown],
                outputs=[char1_custom_style, char1_style_instructions],
            )
            char2_style_dropdown.change(
                fn=update_style_dropdown,
                inputs=[char2_style_dropdown],
                outputs=[char2_custom_style, char2_style_instructions],
            )

            # Event handlers for Rap Battle Audio tab
            generate_lyrics_btn.click(
                fn=handle_generate_all_lyrics,
                inputs=[
                    char1_name,
                    char1_twitter,
                    char2_name,
                    char2_twitter,
                    battle_theme,
                    scene_description,
                ],
                outputs=[grok_verse1, grok_verse2, grok_verse3, grok_verse4, lyrics_status],
            )

            # Audio generation handler (single button for all)
            generate_all_audio_btn.click(
                fn=handle_generate_all_audio,
                inputs=[
                    custom_verse1,
                    custom_verse2,
                    custom_verse3,
                    custom_verse4,
                    grok_verse1,
                    grok_verse2,
                    grok_verse3,
                    grok_verse4,
                    char1_style_instructions,
                    char2_style_instructions,
                ],
                outputs=[
                    verse1_audio,
                    verse2_audio,
                    verse3_audio,
                    verse4_audio,
                    combined_audio,
                    audio_status,
                ],
            )

        with gr.TabItem("Beat Generator"):
            gr.Markdown("Generate beats using Grok AI. Select a style and customize tempo.")

            with gr.Row():
                with gr.Column():
                    style_dropdown = gr.Dropdown(
                        choices=["trap", "boom bap", "west coast", "drill"],
                        value="trap",
                        label="Style",
                    )
                    bpm_slider = gr.Slider(
                        minimum=60, maximum=180, value=140, step=5, label="BPM"
                    )
                    bars_dropdown = gr.Dropdown(
                        choices=[2, 4, 8], value=4, label="Bars"
                    )
                    loops_slider = gr.Slider(
                        minimum=1, maximum=8, value=4, step=1, label="Loops"
                    )
                    generate_beat_btn = gr.Button("Generate Beat", variant="primary")

                with gr.Column():
                    beat_audio = gr.Audio(label="Generated Beat", type="filepath")
                    beat_status = gr.Textbox(label="Status", interactive=False)

            with gr.Accordion("Beat Pattern JSON", open=False):
                beat_json = gr.Code(label="Pattern", language="json")

            generate_beat_btn.click(
                fn=handle_beat_generation,
                inputs=[style_dropdown, bpm_slider, bars_dropdown, loops_slider],
                outputs=[beat_audio, beat_json, beat_status],
            )

        with gr.TabItem("Rap Battle Video"):
            gr.Markdown("""## Rap Battle Video Generator
Generate storyboard images and videos from a rap battle script.

**Format your script with Person A/B markers:**
```
[Person A]
Verse 1 line 1
Verse 1 line 2...

[Person B]
Verse 1 line 1...
```
            """)

            with gr.Row():
                with gr.Column():
                    theme_input = gr.Textbox(
                        label="Theme",
                        placeholder="e.g., medieval, space, cyberpunk, underwater, post-apocalyptic",
                        value="cyberpunk neon city",
                    )
                    script_input = gr.Textbox(
                        label="Rap Script",
                        lines=15,
                        placeholder="""[Person A]
Yo I step into the ring, crown heavy on my head
Medieval bars so cold, leave your kingdom for dead

[Person B]
You call yourself a king? That throne is made of lies
I'm the dragon in the sky, watch your empire die

[Person A]
Back for round two, my sword still sharp and true
Castle walls can't save you from what I'm about to do

[Person B]
Your reign ends tonight, no crown can save your soul
I'll write your name in flames and let the history scroll

[Conclusion]
The battle ends, the crowd roars, who will claim the throne?""",
                    )
                    with gr.Accordion("Character Settings", open=True):
                        with gr.Row():
                            speaker_a_name = gr.Textbox(
                                label="Speaker A Name",
                                placeholder="e.g., Elon Musk",
                                info="Name as it appears in script",
                            )
                            speaker_b_name = gr.Textbox(
                                label="Speaker B Name",
                                placeholder="e.g., Sam Altman",
                                info="Name as it appears in script",
                            )
                        gr.Markdown("**Reference Photos** (for consistent character appearance)")
                        with gr.Row():
                            speaker_a_image = gr.Image(
                                label="Speaker A Photo",
                                type="filepath",
                            )
                            speaker_b_image = gr.Image(
                                label="Speaker B Photo",
                                type="filepath",
                            )
                        char_a_input = gr.Textbox(
                            label="Speaker A Visual Description",
                            value="intense male rapper in streetwear, hood up, gold chains",
                        )
                        char_b_input = gr.Textbox(
                            label="Speaker B Visual Description",
                            value="confident female rapper in urban fashion, braids, bold makeup",
                        )
                    test_mode_checkbox = gr.Checkbox(
                        label="Test Mode (2 turns only - saves API credits)",
                        value=True,
                        info="Generate only A, B, Conclusion instead of full 5 segments",
                    )
                    gr.Markdown("**Audio Clips (one per turn)**")
                    with gr.Row():
                        audio_turn1 = gr.File(
                            label="Turn 1: Person A",
                            file_types=[".mp3", ".wav", ".m4a"],
                        )
                        audio_turn2 = gr.File(
                            label="Turn 2: Person B",
                            file_types=[".mp3", ".wav", ".m4a"],
                        )
                    with gr.Row():
                        audio_turn3 = gr.File(
                            label="Turn 3: Person A (full mode only)",
                            file_types=[".mp3", ".wav", ".m4a"],
                        )
                        audio_turn4 = gr.File(
                            label="Turn 4: Person B (full mode only)",
                            file_types=[".mp3", ".wav", ".m4a"],
                        )
                    beat_upload = gr.File(
                        label="Beat Track (continuous instrumental)",
                        file_types=[".mp3", ".wav", ".m4a"],
                    )

                    with gr.Row():
                        preview_btn = gr.Button("Preview Storyboards", variant="secondary")
                        generate_btn = gr.Button("Generate Full Video", variant="primary")

                with gr.Column():
                    storyboard_gallery = gr.Gallery(
                        label="Storyboard Images",
                        columns=3,
                        height="auto",
                    )
                    video_output = gr.Video(label="Final Battle Video")
                    status_output = gr.Textbox(label="Status", lines=8, interactive=False)

            preview_btn.click(
                fn=handle_storyboard_preview,
                inputs=[script_input, theme_input, char_a_input, char_b_input],
                outputs=[storyboard_gallery, status_output],
            )
            generate_btn.click(
                fn=handle_full_video_generation,
                inputs=[script_input, theme_input, speaker_a_name, speaker_b_name, speaker_a_image, speaker_b_image, test_mode_checkbox, audio_turn1, audio_turn2, audio_turn3, audio_turn4, beat_upload, char_a_input, char_b_input],
                outputs=[storyboard_gallery, video_output, status_output],
            )

        with gr.TabItem("Text Formatter"):
            gr.Markdown("Original demo: UUID session logging test.")
            text_input = gr.Textbox(lines=1, placeholder=None, label="Text input")
            text_output = gr.Textbox(lines=1, placeholder=None, label="Text Output")
            text_input.submit(fn=request_formatter, inputs=[text_input], outputs=[text_output])

app = gr.mount_gradio_app(app, demo, path=CUSTOM_GRADIO_PATH)
