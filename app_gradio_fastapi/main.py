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
from app_gradio_fastapi.services.storyboard_pipeline import run_storyboard_pipeline, run_storyboard_only
from app_gradio_fastapi.config.style_presets import (
    get_dropdown_choices,
    get_preset_path,
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
    audio_turn1,
    audio_turn2,
    audio_turn3,
    audio_turn4,
    beat_file,
    char_a: str,
    char_b: str,
):
    """Generate full rap battle video with 4 turn audio clips + beat."""
    if not script.strip():
        return [], None, "Error: Please enter a rap script"
    if not theme.strip():
        return [], None, "Error: Please enter a theme"

    # Collect audio paths for each turn
    audio_paths = []
    for i, audio_file in enumerate([audio_turn1, audio_turn2, audio_turn3, audio_turn4], 1):
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

        with gr.TabItem("Style Transfer"):
            gr.Markdown("""## Rap Battle Style Transfer
Configure two characters for your rap battle. Each character has a unique voice identity and delivery style.
            """)

            gr.Markdown("### Stage 1: Create Voice + Style References")
            with gr.Row():
                # Character 1
                with gr.Column():
                    gr.Markdown("#### Character 1")
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

            # Dropdown visibility toggles
            char1_style_dropdown.change(
                fn=update_custom_visibility,
                inputs=[char1_style_dropdown],
                outputs=[char1_custom_style],
            )
            char2_style_dropdown.change(
                fn=update_custom_visibility,
                inputs=[char2_style_dropdown],
                outputs=[char2_custom_style],
            )

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
            gr.Markdown("### Stage 2: Generate Lyrics")
            with gr.Row():
                # Character 1 Lyrics
                with gr.Column():
                    gr.Markdown("#### Character 1")
                    char1_lyrics = gr.Textbox(
                        lines=8,
                        placeholder="Enter rap lyrics for Character 1...\n\nExample:\nYo, I'm the first one on the mic,\nSpitting fire bars that you'll like,\nMy flow is cold, my rhymes are tight,\nStep to me? You'll lose the fight!",
                        label="Rap Lyrics",
                    )
                    char1_style_instructions = gr.Textbox(
                        lines=2,
                        placeholder="e.g., aggressive rapper with rhythmic flow",
                        label="Style Instructions",
                        value="aggressive rapper with rhythmic flow",
                    )
                    char1_generate_btn = gr.Button("Generate Rap 1", variant="primary")
                    char1_audio_output = gr.Audio(label="Generated Audio", type="filepath")
                    char1_gen_status = gr.Textbox(label="Status", interactive=False)

                # Character 2 Lyrics
                with gr.Column():
                    gr.Markdown("#### Character 2")
                    char2_lyrics = gr.Textbox(
                        lines=8,
                        placeholder="Enter rap lyrics for Character 2...\n\nExample:\nHold up, let me take the stage,\nI'm about to turn the page,\nMy verses hit with so much rage,\nI'm the champion of this age!",
                        label="Rap Lyrics",
                    )
                    char2_style_instructions = gr.Textbox(
                        lines=2,
                        placeholder="e.g., aggressive rapper with rhythmic flow",
                        label="Style Instructions",
                        value="aggressive rapper with rhythmic flow",
                    )
                    char2_generate_btn = gr.Button("Generate Rap 2", variant="primary")
                    char2_audio_output = gr.Audio(label="Generated Audio", type="filepath")
                    char2_gen_status = gr.Textbox(label="Status", interactive=False)

            # Stage 2 buttons
            char1_generate_btn.click(
                fn=handle_generate_char1,
                inputs=[char1_lyrics, char1_style_instructions],
                outputs=[char1_audio_output, char1_gen_status],
            )
            char2_generate_btn.click(
                fn=handle_generate_char2,
                inputs=[char2_lyrics, char2_style_instructions],
                outputs=[char2_audio_output, char2_gen_status],
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
                        char_a_input = gr.Textbox(
                            label="Speaker A Visual Description",
                            value="intense male rapper in streetwear, hood up, gold chains",
                        )
                        char_b_input = gr.Textbox(
                            label="Speaker B Visual Description",
                            value="confident female rapper in urban fashion, braids, bold makeup",
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
                            label="Turn 3: Person A",
                            file_types=[".mp3", ".wav", ".m4a"],
                        )
                        audio_turn4 = gr.File(
                            label="Turn 4: Person B",
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
                inputs=[script_input, theme_input, speaker_a_name, speaker_b_name, audio_turn1, audio_turn2, audio_turn3, audio_turn4, beat_upload, char_a_input, char_b_input],
                outputs=[storyboard_gallery, video_output, status_output],
            )

        with gr.TabItem("Text Formatter"):
            gr.Markdown("Original demo: UUID session logging test.")
            text_input = gr.Textbox(lines=1, placeholder=None, label="Text input")
            text_output = gr.Textbox(lines=1, placeholder=None, label="Text Output")
            text_input.submit(fn=request_formatter, inputs=[text_input], outputs=[text_output])

app = gr.mount_gradio_app(app, demo, path=CUSTOM_GRADIO_PATH)
