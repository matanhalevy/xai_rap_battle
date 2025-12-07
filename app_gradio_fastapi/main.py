import gradio as gr
from fastapi import FastAPI

from app_gradio_fastapi import routes
from app_gradio_fastapi.helpers.formatters import request_formatter
from app_gradio_fastapi.helpers.session_logger import change_logging
from app_gradio_fastapi.services.voice_api import generate_rap_voice


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

        with gr.TabItem("Text Formatter"):
            gr.Markdown("Original demo: UUID session logging test.")
            text_input = gr.Textbox(lines=1, placeholder=None, label="Text input")
            text_output = gr.Textbox(lines=1, placeholder=None, label="Text Output")
            text_input.submit(fn=request_formatter, inputs=[text_input], outputs=[text_output])

app = gr.mount_gradio_app(app, demo, path=CUSTOM_GRADIO_PATH)
