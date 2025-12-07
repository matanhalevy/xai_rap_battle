import gradio as gr
from fastapi import FastAPI

from app_gradio_fastapi import routes
from app_gradio_fastapi.helpers.formatters import request_formatter
from app_gradio_fastapi.helpers.session_logger import change_logging
from app_gradio_fastapi.services.voice_api import generate_rap_voice
from app_gradio_fastapi.services.elevenlabs_api import create_style_reference
from app_gradio_fastapi.services.beat_api import generate_beat_pattern
from app_gradio_fastapi.services.beat_generator import get_generator


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


# Store the last created style reference for use in Stage 2
_style_reference_cache = {"path": None, "voice_id": None}


def handle_create_style_reference(
    voice_identity_file,
    style_source_file,
    reference_name: str,
    celebrity_mode: bool,
    stability: float,
    similarity_boost: float,
):
    """Stage 1: Create voice+style reference from two audio files."""
    if voice_identity_file is None:
        return None, "Error: Please upload a voice identity file"
    if style_source_file is None:
        return None, "Error: Please upload a style source file"

    # Get file paths from Gradio file objects
    voice_path = voice_identity_file.name if hasattr(voice_identity_file, "name") else voice_identity_file
    style_path = style_source_file.name if hasattr(style_source_file, "name") else style_source_file

    name = reference_name.strip() if reference_name.strip() else "custom_voice"

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
        _style_reference_cache["path"] = output_path
        _style_reference_cache["voice_id"] = voice_id

    return output_path, status


def handle_generate_with_style(lyrics: str, style_reference_file, style_instructions: str):
    """Stage 2: Generate new lyrics using the style reference."""
    if not lyrics.strip():
        return None, "Error: Please enter rap lyrics"

    # Use uploaded file or cached reference
    if style_reference_file is not None:
        ref_path = style_reference_file.name if hasattr(style_reference_file, "name") else style_reference_file
    elif _style_reference_cache["path"]:
        ref_path = _style_reference_cache["path"]
    else:
        return None, "Error: Please create a style reference first (Stage 1) or upload one"

    # Use xAI TTS with the style reference as voice sample
    audio_path, status = generate_rap_voice(
        lyrics=lyrics,
        style_instructions=style_instructions if style_instructions.strip() else "aggressive rapper with rhythmic flow",
        voice_file=ref_path,
    )
    return audio_path, status


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
            gr.Markdown("""## Voice Style Transfer
Transform one voice into another while preserving delivery style and cadence.

**Stage 1**: Combine a voice identity (e.g., Elon) with a delivery style (e.g., Stormzy's rap)
**Stage 2**: Generate new lyrics using the combined voice+style
            """)

            gr.Markdown("### Stage 1: Create Voice + Style Reference")
            with gr.Row():
                with gr.Column():
                    voice_identity_upload = gr.File(
                        label="Voice Identity (who to sound like)",
                        file_types=[".mp3", ".m4a", ".wav"],
                    )
                    style_source_upload = gr.File(
                        label="Style Source (delivery/cadence to copy)",
                        file_types=[".mp3", ".m4a", ".wav"],
                    )
                    reference_name_input = gr.Textbox(
                        label="Reference Name",
                        value="custom_voice",
                        placeholder="e.g., Elon Rapper",
                    )
                    celebrity_mode_checkbox = gr.Checkbox(
                        label="Celebrity Voice Mode",
                        value=False,
                        info="Enable if ElevenLabs blocks the voice. Applies pitch shifting to evade detection.",
                    )
                    with gr.Accordion("Voice Settings", open=True):
                        similarity_slider = gr.Slider(
                            minimum=0.0,
                            maximum=1.0,
                            value=0.85,
                            step=0.05,
                            label="Similarity Boost",
                            info="Higher = more like voice identity. Try 0.9+ if output sounds too much like style source.",
                        )
                        stability_slider = gr.Slider(
                            minimum=0.0,
                            maximum=1.0,
                            value=0.5,
                            step=0.05,
                            label="Stability",
                            info="Higher = more consistent voice. Lower = more expressive/variable.",
                        )
                    create_reference_btn = gr.Button("Create Style Reference", variant="primary")

                with gr.Column():
                    reference_audio_output = gr.Audio(
                        label="Style Reference Output",
                        type="filepath",
                    )
                    reference_status_output = gr.Textbox(label="Status", interactive=False)

            create_reference_btn.click(
                fn=handle_create_style_reference,
                inputs=[
                    voice_identity_upload,
                    style_source_upload,
                    reference_name_input,
                    celebrity_mode_checkbox,
                    stability_slider,
                    similarity_slider,
                ],
                outputs=[reference_audio_output, reference_status_output],
            )

            gr.Markdown("---")
            gr.Markdown("### Stage 2: Generate New Lyrics with Style")
            with gr.Row():
                with gr.Column():
                    style_lyrics_input = gr.Textbox(
                        lines=8,
                        placeholder="Enter your rap lyrics here...\n\nExample:\nYo, I'm Elon and I'm here to say,\nBuilding rockets every single day,\nMars is calling, we're on our way,\nSpaceX rockets, no delay!",
                        label="Rap Lyrics",
                    )
                    style_reference_upload = gr.File(
                        label="Style Reference (optional - uses Stage 1 output if empty)",
                        file_types=[".mp3", ".m4a", ".wav"],
                    )
                    style_instructions_input = gr.Textbox(
                        lines=2,
                        placeholder="e.g., aggressive rapper with rhythmic flow",
                        label="Additional Style Instructions",
                        value="aggressive rapper with rhythmic flow",
                    )
                    generate_style_btn = gr.Button("Generate Rap with Style", variant="primary")

                with gr.Column():
                    style_audio_output = gr.Audio(label="Generated Audio", type="filepath")
                    style_status_output = gr.Textbox(label="Status", interactive=False)

            generate_style_btn.click(
                fn=handle_generate_with_style,
                inputs=[style_lyrics_input, style_reference_upload, style_instructions_input],
                outputs=[style_audio_output, style_status_output],
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

        with gr.TabItem("Text Formatter"):
            gr.Markdown("Original demo: UUID session logging test.")
            text_input = gr.Textbox(lines=1, placeholder=None, label="Text input")
            text_output = gr.Textbox(lines=1, placeholder=None, label="Text Output")
            text_input.submit(fn=request_formatter, inputs=[text_input], outputs=[text_output])

app = gr.mount_gradio_app(app, demo, path=CUSTOM_GRADIO_PATH)
