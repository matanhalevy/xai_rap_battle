# Grok Voice Rap Battle - Technical Specification

## Track Info
- **Track:** Grok Voice
- **Focus:** Grok Voice API integrations
- **Track Leads:** Scott Fitzgerald + Boyan Lin
- **Office Hours:** Saturday 5pm - 9pm @ Point Reyes
- **Slack:** #track-grok-voice

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend Framework | FastAPI (Python 3.11+) |
| Frontend | Gradio |
| Task Queue | asyncio (simple) or Celery + Redis (if needed) |
| AI - Text/Video | Grok API |
| AI - Voice | **Grok Voice API (primary)** / ElevenLabs (fallback) |
| AI - Music | TBD at hackathon (Grok or Suno/Udio if available) |
| Audio Processing | pydub, librosa |
| Video Processing | moviepy, ffmpeg |
| Storage | Local filesystem (hackathon), S3-compatible (production) |

---

## Project Structure

```
grok-rap-battle/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Environment variables, API keys
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py           # API endpoints
│   │   └── websocket.py        # Progress updates (optional)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # Pipeline coordination
│   │   ├── beat_generator.py   # Beat generation service
│   │   ├── lyric_generator.py  # Grok text API wrapper
│   │   ├── voice_synth.py      # ElevenLabs integration
│   │   ├── audio_mixer.py      # Audio production
│   │   └── video_generator.py  # Grok video API wrapper
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic models
│   └── utils/
│       ├── __init__.py
│       ├── audio.py            # Audio helpers
│       ├── video.py            # Video helpers
│       └── youtube.py          # Voice sample extraction
├── gradio_app/
│   ├── __init__.py
│   └── interface.py            # Gradio UI definition
├── assets/
│   ├── voice_samples/          # Pre-extracted character voices
│   ├── face_images/            # Character reference photos
│   └── demo/                   # Sample outputs
├── outputs/                    # Generated content
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

---

## Data Schemas

```python
# app/models/schemas.py

from pydantic import BaseModel
from enum import Enum
from typing import Optional

class RapStyle(str, Enum):
    AGGRESSIVE = "aggressive"
    LYRICAL = "lyrical"
    COMEDIC = "comedic"
    MELODIC = "melodic"
    INTELLECTUAL = "intellectual"

class SceneSetting(str, Enum):
    WAREHOUSE = "warehouse"      # 8 Mile style
    STAGE = "stage"              # Epic Rap Battles style
    STREET = "street"
    STUDIO = "studio"
    CUSTOM = "custom"

class CharacterInput(BaseModel):
    name: str
    rap_style: RapStyle = RapStyle.AGGRESSIVE
    voice_sample_path: Optional[str] = None      # Path to audio file for cloning
    face_image_path: Optional[str] = None        # Path to reference image
    artist_reference: Optional[str] = None       # Style hint (e.g., "Eminem aggressive flow")
    beat_style_hint: Optional[str] = None        # Beat context for voice delivery
    
class BattleRequest(BaseModel):
    character_1: CharacterInput
    character_2: CharacterInput
    topic: str
    topic_context: Optional[str] = None          # Additional context
    scene_setting: SceneSetting = SceneSetting.STAGE
    num_verses: int = 2                          # Verses per character before finale
    
class BeatMetadata(BaseModel):
    bpm: int
    bars: int
    duration_seconds: float
    style: str
    audio_path: str

class Verse(BaseModel):
    character_name: str
    verse_number: int
    lyrics: str
    is_finale: bool = False
    
class LyricsOutput(BaseModel):
    verses: list[Verse]
    total_duration_estimate: float

class VoiceOutput(BaseModel):
    character_name: str
    verse_number: int
    audio_path: str
    duration_seconds: float

class AudioMixOutput(BaseModel):
    mixed_audio_path: str
    duration_seconds: float
    
class VideoOutput(BaseModel):
    video_path: str
    duration_seconds: float
    resolution: str

class BattleResponse(BaseModel):
    battle_id: str
    status: str
    beat: Optional[BeatMetadata] = None
    lyrics: Optional[LyricsOutput] = None
    voice_tracks: Optional[list[VoiceOutput]] = None
    mixed_audio: Optional[AudioMixOutput] = None
    final_video: Optional[VideoOutput] = None
    error: Optional[str] = None

class PipelineStatus(BaseModel):
    battle_id: str
    current_stage: str
    stages_completed: list[str]
    progress_percent: int
    message: str
```

---

## API Endpoints

```python
# app/api/routes.py

from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.models.schemas import BattleRequest, BattleResponse, PipelineStatus

router = APIRouter(prefix="/api/v1")

@router.post("/battle", response_model=BattleResponse)
async def create_battle(request: BattleRequest, background_tasks: BackgroundTasks):
    """
    Initiate a new rap battle generation.
    Returns battle_id immediately, processing happens in background.
    """
    pass

@router.get("/battle/{battle_id}", response_model=BattleResponse)
async def get_battle(battle_id: str):
    """Get current state of a battle generation."""
    pass

@router.get("/battle/{battle_id}/status", response_model=PipelineStatus)
async def get_battle_status(battle_id: str):
    """Get detailed pipeline progress."""
    pass

@router.delete("/battle/{battle_id}")
async def cancel_battle(battle_id: str):
    """Cancel an in-progress battle generation."""
    pass

# Individual stage endpoints (for testing/debugging)

@router.post("/generate/beat")
async def generate_beat(style: str, duration_seconds: int = 120):
    """Generate beat only."""
    pass

@router.post("/generate/lyrics")
async def generate_lyrics(request: BattleRequest, beat_metadata: BeatMetadata):
    """Generate lyrics only."""
    pass

@router.post("/generate/voice")
async def generate_voice(lyrics: str, voice_sample_path: str):
    """Generate voice for single verse."""
    pass

@router.post("/generate/video")
async def generate_video(audio_path: str, character_faces: list[str], setting: SceneSetting):
    """Generate video only."""
    pass

# Utility endpoints

@router.get("/characters/presets")
async def list_preset_characters():
    """List pre-configured demo characters with voice samples."""
    pass

@router.post("/voice-sample/extract")
async def extract_voice_sample(youtube_url: str, start_time: int, duration: int):
    """Extract voice sample from YouTube for cloning."""
    pass
```

---

## Pipeline Orchestration

```python
# app/services/orchestrator.py

import asyncio
from uuid import uuid4
from app.models.schemas import BattleRequest, BattleResponse, PipelineStatus

class BattlePipeline:
    """Orchestrates the full rap battle generation pipeline."""
    
    STAGES = [
        "beat_generation",
        "lyric_generation", 
        "voice_synthesis",
        "audio_mixing",
        "video_generation"
    ]
    
    def __init__(self, request: BattleRequest):
        self.battle_id = str(uuid4())
        self.request = request
        self.current_stage = None
        self.completed_stages = []
        self.artifacts = {}
        self.status_callbacks = []
        
    async def run(self) -> BattleResponse:
        """Execute full pipeline."""
        try:
            # Stage 1: Beat Generation
            await self._update_status("beat_generation")
            self.artifacts["beat"] = await self._generate_beat()
            
            # Stage 2: Lyric Generation
            await self._update_status("lyric_generation")
            self.artifacts["lyrics"] = await self._generate_lyrics()
            
            # Stage 3: Voice Synthesis (parallel per character)
            await self._update_status("voice_synthesis")
            self.artifacts["voices"] = await self._synthesize_voices()
            
            # Stage 4: Audio Mixing
            await self._update_status("audio_mixing")
            self.artifacts["mixed_audio"] = await self._mix_audio()
            
            # Stage 5: Video Generation
            await self._update_status("video_generation")
            self.artifacts["video"] = await self._generate_video()
            
            return self._build_response(status="completed")
            
        except Exception as e:
            return self._build_response(status="failed", error=str(e))
    
    async def _generate_beat(self):
        """Generate instrumental beat."""
        from app.services.beat_generator import BeatGenerator
        generator = BeatGenerator()
        return await generator.generate(
            style=self._infer_beat_style(),
            duration=self._calculate_duration()
        )
    
    async def _generate_lyrics(self):
        """Generate battle lyrics verse by verse."""
        from app.services.lyric_generator import LyricGenerator
        generator = LyricGenerator()
        
        verses = []
        battle_context = []
        
        # Alternating verses
        for verse_num in range(self.request.num_verses):
            for char in [self.request.character_1, self.request.character_2]:
                verse = await generator.generate_verse(
                    character=char,
                    opponent=self._get_opponent(char),
                    topic=self.request.topic,
                    beat_metadata=self.artifacts["beat"],
                    previous_verses=battle_context,
                    is_finale=False
                )
                verses.append(verse)
                battle_context.append(verse)
        
        # Final verses (longer closers)
        for char in [self.request.character_1, self.request.character_2]:
            verse = await generator.generate_verse(
                character=char,
                opponent=self._get_opponent(char),
                topic=self.request.topic,
                beat_metadata=self.artifacts["beat"],
                previous_verses=battle_context,
                is_finale=True
            )
            verses.append(verse)
            battle_context.append(verse)
            
        return verses
    
    async def _synthesize_voices(self):
        """Generate voice audio for all verses."""
        from app.services.voice_synth import VoiceSynthesizer
        synth = VoiceSynthesizer()
        
        tasks = []
        for verse in self.artifacts["lyrics"]:
            char = self._get_character(verse.character_name)
            tasks.append(
                synth.synthesize(
                    text=verse.lyrics,
                    voice_sample=char.voice_sample_path,
                    style="rap"
                )
            )
        
        return await asyncio.gather(*tasks)
    
    async def _mix_audio(self):
        """Mix vocals with beat."""
        from app.services.audio_mixer import AudioMixer
        mixer = AudioMixer()
        return await mixer.mix(
            beat=self.artifacts["beat"],
            vocals=self.artifacts["voices"]
        )
    
    async def _generate_video(self):
        """Generate final video with lip sync."""
        from app.services.video_generator import VideoGenerator
        generator = VideoGenerator()
        return await generator.generate(
            audio_path=self.artifacts["mixed_audio"].audio_path,
            characters=[self.request.character_1, self.request.character_2],
            setting=self.request.scene_setting
        )
```

---

## Service Implementations

### Lyric Generator (Grok API)

```python
# app/services/lyric_generator.py

import httpx
from app.config import settings
from app.models.schemas import CharacterInput, BeatMetadata, Verse

class LyricGenerator:
    """Generate rap lyrics using Grok API."""
    
    GROK_API_BASE = "https://api.x.ai/v1"
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {settings.GROK_API_KEY}"}
        )
    
    async def generate_verse(
        self,
        character: CharacterInput,
        opponent: CharacterInput,
        topic: str,
        beat_metadata: BeatMetadata,
        previous_verses: list[Verse],
        is_finale: bool
    ) -> Verse:
        
        prompt = self._build_prompt(
            character, opponent, topic, beat_metadata, previous_verses, is_finale
        )
        
        response = await self.client.post(
            f"{self.GROK_API_BASE}/chat/completions",
            json={
                "model": "grok-2-latest",  # Or whatever model is available
                "messages": [
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.9,
                "max_tokens": 500
            }
        )
        
        lyrics = response.json()["choices"][0]["message"]["content"]
        
        return Verse(
            character_name=character.name,
            verse_number=len([v for v in previous_verses if v.character_name == character.name]) + 1,
            lyrics=lyrics,
            is_finale=is_finale
        )
    
    def _system_prompt(self) -> str:
        return """You are a legendary rap battle lyricist. Write verses that:
- Reference the opponent's previous bars with clever rebuttals
- Include wordplay, punchlines, and topic-specific references
- Match the character's known personality and speech patterns
- Follow the beat structure provided (bars and syllable counts)
- Build intensity toward the finale

Output ONLY the lyrics, no annotations or explanations."""

    def _build_prompt(self, character, opponent, topic, beat, verses, is_finale) -> str:
        verse_history = "\n\n".join([
            f"[{v.character_name}]: {v.lyrics}" for v in verses
        ]) if verses else "This is the opening verse."
        
        verse_type = "FINALE (longer, most intense, mic drop ending)" if is_finale else "standard verse"
        bars = beat.bars * 2 if is_finale else beat.bars
        
        return f"""Write a {verse_type} for {character.name} in a rap battle against {opponent.name}.

TOPIC: {topic}

BEAT INFO:
- BPM: {beat.bpm}
- Bars needed: {bars}
- Style: {beat.style}

CHARACTER STYLE: {character.rap_style.value}

BATTLE SO FAR:
{verse_history}

Write {character.name}'s next verse. Be savage but clever."""
```

### Voice Synthesizer (Grok Voice API + ElevenLabs Fallback)

```python
# app/services/voice_synth.py

import httpx
from abc import ABC, abstractmethod
from app.config import settings

class VoiceSynthesizerBase(ABC):
    """Abstract base for voice synthesis providers."""
    
    @abstractmethod
    async def synthesize(self, text: str, voice_config: dict, style: str = "rap") -> str:
        """Generate speech audio from text. Returns path to audio file."""
        pass


class GrokVoiceSynthesizer(VoiceSynthesizerBase):
    """
    Voice synthesis using Grok Voice API (PRIMARY).
    
    Capabilities confirmed at hackathon:
    - Voice cloning: YES - provide a short sample (e.g., "quick brown fox" phrase)
    - Rhythmic delivery: Prompt-based - include artist samples, beat hints, cadence
    - Emotion/style: Controlled via prompt
    - Output: Real-time streaming OR pre-rendered
    """
    
    GROK_VOICE_API_BASE = "https://api.x.ai/v1"
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {settings.GROK_API_KEY}"},
            timeout=120.0
        )
        self.cloned_voices = {}  # Cache cloned voice IDs
    
    async def clone_voice(self, name: str, audio_sample: str) -> str:
        """
        Clone a voice from a short audio sample.
        Sample can be as short as a "quick brown fox" phrase.
        """
        with open(audio_sample, "rb") as f:
            response = await self.client.post(
                f"{self.GROK_VOICE_API_BASE}/voice/clone",
                files={"audio": f},
                data={"name": name}
            )
        
        voice_id = response.json().get("voice_id")
        self.cloned_voices[name] = voice_id
        return voice_id
    
    async def synthesize(
        self, 
        text: str, 
        voice_config: dict,
        style: str = "rap"
    ) -> str:
        """
        Generate speech audio from text using Grok Voice.
        
        voice_config:
        - voice_sample: path to audio file for cloning
        - character_name: name for caching cloned voice
        - artist_reference: (optional) artist style hints
        - beat_style: (optional) beat/rhythm hints
        - cadence: (optional) flow speed hints
        
        Style/emotion is controlled via prompt engineering.
        """
        
        # Clone voice if not already cached
        character_name = voice_config.get("character_name", "default")
        voice_id = self.cloned_voices.get(character_name)
        
        if not voice_id and voice_config.get("voice_sample"):
            voice_id = await self.clone_voice(
                character_name, 
                voice_config["voice_sample"]
            )
        
        # Build style prompt for rhythmic delivery
        style_prompt = self._build_style_prompt(voice_config, style)
        
        # Generate audio (pre-rendered mode for rap verses)
        response = await self.client.post(
            f"{self.GROK_VOICE_API_BASE}/voice/synthesize",
            json={
                "text": text,
                "voice_id": voice_id,
                "style_prompt": style_prompt,
                "mode": "prerendered"  # Use prerendered for consistent timing
            }
        )
        
        output_path = f"outputs/voice_grok_{character_name}_{hash(text)}.mp3"
        with open(output_path, "wb") as f:
            f.write(response.content)
        
        return output_path
    
    def _build_style_prompt(self, voice_config: dict, style: str) -> str:
        """
        Build a style prompt to guide rhythmic/emotional delivery.
        Grok Voice uses prompt-based style control.
        """
        parts = []
        
        # Base style
        if style == "rap":
            parts.append("Deliver as a rap verse with rhythmic flow and emphasis on rhymes.")
        
        # Artist reference
        if voice_config.get("artist_reference"):
            parts.append(f"Style inspired by: {voice_config['artist_reference']}")
        
        # Beat hints
        if voice_config.get("beat_style"):
            parts.append(f"Beat style: {voice_config['beat_style']}")
        
        # Cadence
        cadence = voice_config.get("cadence", "aggressive")
        cadence_map = {
            "aggressive": "Fast, punchy delivery with hard consonants",
            "lyrical": "Smooth, flowing delivery with melodic emphasis",
            "comedic": "Playful timing with comedic pauses and emphasis",
            "melodic": "Sing-song delivery with pitch variation",
            "intellectual": "Measured, precise delivery with clear enunciation"
        }
        parts.append(cadence_map.get(cadence, cadence_map["aggressive"]))
        
        # Emotion for battle context
        parts.append("Emotion: Confident, competitive, energetic")
        
        return " | ".join(parts)
    
    async def synthesize_realtime(self, text: str, voice_config: dict):
        """
        Real-time streaming synthesis (for future live features).
        Returns an async generator of audio chunks.
        """
        # TODO: Implement WebSocket streaming if needed
        pass
    
    @staticmethod
    def is_available() -> bool:
        """Check if Grok Voice API is configured and accessible."""
        return bool(settings.GROK_API_KEY)


class ElevenLabsSynthesizer(VoiceSynthesizerBase):
    """Voice synthesis using ElevenLabs API (FALLBACK)."""
    
    ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            headers={"xi-api-key": settings.ELEVENLABS_API_KEY}
        )
        self.cloned_voices = {}
    
    async def clone_voice(self, name: str, audio_path: str) -> str:
        """Clone a voice from audio sample, return voice_id."""
        
        with open(audio_path, "rb") as f:
            response = await self.client.post(
                f"{self.ELEVENLABS_API_BASE}/voices/add",
                data={"name": name},
                files={"files": f}
            )
        
        voice_id = response.json()["voice_id"]
        self.cloned_voices[name] = voice_id
        return voice_id
    
    async def synthesize(
        self, 
        text: str, 
        voice_config: dict,
        style: str = "rap"
    ) -> str:
        """Generate speech audio from text using ElevenLabs."""
        
        voice_sample = voice_config.get("voice_sample")
        voice_id = self.cloned_voices.get(voice_sample)
        
        if not voice_id and voice_sample:
            voice_id = await self.clone_voice(voice_sample, voice_sample)
        
        response = await self.client.post(
            f"{self.ELEVENLABS_API_BASE}/text-to-speech/{voice_id}",
            json={
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.3,
                    "similarity_boost": 0.8,
                    "style": 0.7,
                    "use_speaker_boost": True
                }
            }
        )
        
        output_path = f"outputs/voice_eleven_{voice_id}_{hash(text)}.mp3"
        with open(output_path, "wb") as f:
            f.write(response.content)
        
        return output_path
    
    @staticmethod
    def is_available() -> bool:
        """Check if ElevenLabs API is configured."""
        return bool(settings.ELEVENLABS_API_KEY)


class VoiceSynthesizer:
    """
    Factory that selects the best available voice synthesis provider.
    Prioritizes Grok Voice, falls back to ElevenLabs.
    """
    
    def __init__(self, force_provider: str = None):
        if force_provider == "elevenlabs":
            self.provider = ElevenLabsSynthesizer()
        elif force_provider == "grok":
            self.provider = GrokVoiceSynthesizer()
        else:
            # Auto-select: prefer Grok Voice
            if GrokVoiceSynthesizer.is_available():
                self.provider = GrokVoiceSynthesizer()
                print("Using Grok Voice API for synthesis")
            elif ElevenLabsSynthesizer.is_available():
                self.provider = ElevenLabsSynthesizer()
                print("Using ElevenLabs API for synthesis (fallback)")
            else:
                raise RuntimeError("No voice synthesis provider available")
    
    async def synthesize(self, text: str, voice_config: dict, style: str = "rap") -> str:
        return await self.provider.synthesize(text, voice_config, style)
```

### Video Generator (Grok Video API)

```python
# app/services/video_generator.py

import httpx
from app.config import settings
from app.models.schemas import CharacterInput, SceneSetting

class VideoGenerator:
    """Generate rap battle video using Grok Video API."""
    
    GROK_API_BASE = "https://api.x.ai/v1"
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {settings.GROK_API_KEY}"},
            timeout=300.0  # Video generation takes time
        )
    
    async def generate(
        self,
        audio_path: str,
        characters: list[CharacterInput],
        setting: SceneSetting
    ) -> str:
        """Generate video synced to audio. Returns path to video file."""
        
        # Build scene prompt
        scene_prompt = self._build_scene_prompt(characters, setting)
        
        # Load character face images
        face_images = [
            self._encode_image(c.face_image_path) for c in characters
        ]
        
        # Load audio
        audio_data = self._encode_audio(audio_path)
        
        # Call Grok Video API
        # NOTE: Exact API shape TBD based on hackathon access
        response = await self.client.post(
            f"{self.GROK_API_BASE}/video/generate",
            json={
                "prompt": scene_prompt,
                "reference_images": face_images,
                "audio": audio_data,
                "settings": {
                    "lip_sync": True,
                    "duration": "match_audio",
                    "resolution": "1080p",
                    "fps": 30
                }
            }
        )
        
        # Save video
        output_path = f"outputs/battle_{hash(audio_path)}.mp4"
        with open(output_path, "wb") as f:
            f.write(response.content)
        
        return output_path
    
    def _build_scene_prompt(self, characters: list[CharacterInput], setting: SceneSetting) -> str:
        setting_descriptions = {
            SceneSetting.WAREHOUSE: "dimly lit industrial warehouse, concrete floors, hanging lights, crowd in shadows, 8 Mile style",
            SceneSetting.STAGE: "professional stage with dramatic lighting, Epic Rap Battles of History style, historical backdrop",
            SceneSetting.STREET: "urban street corner at night, graffiti walls, street lights, small crowd gathered",
            SceneSetting.STUDIO: "professional recording studio, sound panels, microphones, intimate setting"
        }
        
        return f"""Rap battle video scene:
Setting: {setting_descriptions[setting]}
Character 1: {characters[0].name} - rapping aggressively, confident posture
Character 2: {characters[1].name} - reacting, waiting for their turn
Camera: Dynamic angles, close-ups during verses, wide shots during transitions
Style: Cinematic, high energy, dramatic lighting"""
```

---

## Gradio Interface

```python
# gradio_app/interface.py

import gradio as gr
from app.services.orchestrator import BattlePipeline
from app.models.schemas import BattleRequest, CharacterInput, RapStyle, SceneSetting

# Pre-configured demo characters
PRESET_CHARACTERS = {
    "Elon Musk": {
        "voice_sample": "assets/voice_samples/elon_musk.mp3",
        "face_image": "assets/face_images/elon_musk.jpg",
        "artist_reference": "Tech entrepreneur, confident, slightly awkward cadence"
    },
    "Sam Altman": {
        "voice_sample": "assets/voice_samples/sam_altman.mp3",
        "face_image": "assets/face_images/sam_altman.jpg",
        "artist_reference": "Calm, measured, intellectual Silicon Valley style"
    },
    "Mark Zuckerberg": {
        "voice_sample": "assets/voice_samples/mark_zuckerberg.mp3",
        "face_image": "assets/face_images/mark_zuckerberg.jpg",
        "artist_reference": "Robotic precision, monotone with occasional intensity"
    },
    # Add more as needed
}

async def generate_battle(
    char1_name: str,
    char1_style: str,
    char2_name: str,
    char2_style: str,
    topic: str,
    setting: str,
    num_verses: int,
    progress=gr.Progress()
):
    """Main generation function called by Gradio."""
    
    progress(0, desc="Initializing battle...")
    
    request = BattleRequest(
        character_1=CharacterInput(
            name=char1_name,
            rap_style=RapStyle(char1_style),
            voice_sample_path=PRESET_CHARACTERS[char1_name]["voice_sample"],
            face_image_path=PRESET_CHARACTERS[char1_name]["face_image"],
            artist_reference=PRESET_CHARACTERS[char1_name].get("artist_reference")
        ),
        character_2=CharacterInput(
            name=char2_name,
            rap_style=RapStyle(char2_style),
            voice_sample_path=PRESET_CHARACTERS[char2_name]["voice_sample"],
            face_image_path=PRESET_CHARACTERS[char2_name]["face_image"],
            artist_reference=PRESET_CHARACTERS[char2_name].get("artist_reference")
        ),
        topic=topic,
        scene_setting=SceneSetting(setting),
        num_verses=num_verses
    )
    
    pipeline = BattlePipeline(request)
    
    # Run pipeline with progress updates
    result = await pipeline.run()
    
    if result.status == "completed":
        return (
            result.final_video.video_path,  # Video output
            result.lyrics.verses,            # Lyrics display
            result.mixed_audio.mixed_audio_path  # Audio player
        )
    else:
        raise gr.Error(f"Generation failed: {result.error}")


def create_interface():
    """Build the Gradio interface."""
    
    with gr.Blocks(title="Grok DJ Rap Battle", theme=gr.themes.Dark()) as demo:
        gr.Markdown("# 🎤 Grok DJ Rap Battle Generator")
        gr.Markdown("Create AI-generated rap battles between any two public figures!")
        
        with gr.Row():
            with gr.Column():
                gr.Markdown("### Character 1")
                char1_name = gr.Dropdown(
                    choices=list(PRESET_CHARACTERS.keys()),
                    label="Select Character",
                    value="Elon Musk"
                )
                char1_style = gr.Dropdown(
                    choices=[s.value for s in RapStyle],
                    label="Rap Style",
                    value="aggressive"
                )
            
            with gr.Column():
                gr.Markdown("### Character 2")
                char2_name = gr.Dropdown(
                    choices=list(PRESET_CHARACTERS.keys()),
                    label="Select Character",
                    value="Sam Altman"
                )
                char2_style = gr.Dropdown(
                    choices=[s.value for s in RapStyle],
                    label="Rap Style",
                    value="intellectual"
                )
        
        topic = gr.Textbox(
            label="Battle Topic",
            placeholder="e.g., The OpenAI breakup, Who will achieve AGI first",
            value="The OpenAI breakup"
        )
        
        with gr.Row():
            setting = gr.Dropdown(
                choices=[s.value for s in SceneSetting],
                label="Scene Setting",
                value="stage"
            )
            num_verses = gr.Slider(
                minimum=1,
                maximum=3,
                value=2,
                step=1,
                label="Verses per Character (before finale)"
            )
        
        generate_btn = gr.Button("🎬 Generate Rap Battle", variant="primary", size="lg")
        
        gr.Markdown("---")
        gr.Markdown("### Output")
        
        with gr.Row():
            video_output = gr.Video(label="Final Battle Video")
            
        with gr.Row():
            audio_output = gr.Audio(label="Audio Track")
            lyrics_output = gr.JSON(label="Generated Lyrics")
        
        generate_btn.click(
            fn=generate_battle,
            inputs=[char1_name, char1_style, char2_name, char2_style, topic, setting, num_verses],
            outputs=[video_output, lyrics_output, audio_output]
        )
    
    return demo


if __name__ == "__main__":
    demo = create_interface()
    demo.launch()
```

---

## Configuration

```python
# app/config.py

from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API Keys
    GROK_API_KEY: str
    ELEVENLABS_API_KEY: Optional[str] = None  # Fallback only
    
    # Voice Provider Selection
    VOICE_PROVIDER: Optional[str] = None  # "grok", "elevenlabs", or None (auto)
    
    # Paths
    ASSETS_DIR: str = "assets"
    OUTPUTS_DIR: str = "outputs"
    
    # Defaults
    DEFAULT_BPM: int = 90
    DEFAULT_BARS_PER_VERSE: int = 16
    MAX_VERSES: int = 3
    
    class Config:
        env_file = ".env"

settings = Settings()
```

```bash
# .env.example

# Required
GROK_API_KEY=your_grok_api_key_here

# Optional - Fallback voice synthesis
ELEVENLABS_API_KEY=your_elevenlabs_key_here

# Optional - Force voice provider ("grok" or "elevenlabs")
# Leave unset for auto-selection (prefers Grok Voice)
# VOICE_PROVIDER=grok
```

---

## Dependencies

```txt
# requirements.txt

# Web framework
fastapi>=0.109.0
uvicorn>=0.27.0
python-multipart>=0.0.6

# Gradio
gradio>=4.14.0

# HTTP client
httpx>=0.26.0

# Audio processing
pydub>=0.25.1
librosa>=0.10.1

# Video processing
moviepy>=1.0.3

# Data validation
pydantic>=2.5.0
pydantic-settings>=2.1.0

# Async
asyncio
aiofiles>=23.2.1

# Utils
python-dotenv>=1.0.0
yt-dlp>=2024.1.0  # YouTube audio extraction
```

---

## Implementation Timeline (Hackathon)

### Day 1 - Foundation (Hours 1-8)

| Hour | Task |
|------|------|
| 1-2 | Project setup, dependencies, folder structure |
| 2-3 | Config, schemas, basic FastAPI app |
| 3-4 | Extract voice samples for demo characters |
| 4-5 | Lyric generator service (Grok API) |
| 5-6 | Voice synthesis service (ElevenLabs) |
| 6-7 | Basic audio mixing (beat + vocals) |
| 7-8 | Test text → voice → audio pipeline end-to-end |

### Day 2 - Integration (Hours 9-16)

| Hour | Task |
|------|------|
| 9-10 | Beat generation integration |
| 10-11 | Video generation service (Grok Video) |
| 11-13 | Pipeline orchestration |
| 13-15 | Gradio interface |
| 15-16 | End-to-end testing |

### Final Hours - Polish

| Task |
|------|
| Bug fixes |
| Demo preparation |
| Backup demo video (pre-generated) |

---

## Grok Voice API - Confirmed Capabilities

**Voice Cloning:** ✅ YES
- Accepts short audio samples (even "quick brown fox" phrase works)
- Clone once, reuse voice_id for all verses

**Rhythmic/Rap Delivery:** ✅ Prompt-based
- Include artist reference samples in prompt
- Specify beat style hints
- Control cadence (fast/slow, aggressive/smooth)

**Emotion/Style Control:** ✅ Via prompt
- All style control is done through prompt engineering
- Can combine multiple style hints

**Output Modes:**
- **Real-time:** Streaming for live use cases
- **Pre-rendered:** Better for our use case (consistent timing for mixing)

---

## Voice Config Schema

```python
# Updated voice_config structure for GrokVoiceSynthesizer

voice_config = {
    "voice_sample": "assets/voice_samples/elon_musk.mp3",  # For cloning
    "character_name": "Elon Musk",                         # Cache key
    "artist_reference": "Eminem aggressive flow",          # Style hint
    "beat_style": "boom bap, 90 BPM",                      # Beat context
    "cadence": "aggressive"  # aggressive|lyrical|comedic|melodic|intellectual
}
```

---

## Fallback Strategies

| Component | Primary | Fallback |
|-----------|---------|----------|
| Beat | Grok/Suno | Pre-made royalty-free beats |
| Lyrics | Grok API | GPT-4 / Claude |
| Voice | **Grok Voice API** | **ElevenLabs API** |
| Video | Grok Video | Static images + audio slideshow |

---

## Open Questions for Hackathon

### Grok Voice API - ✅ ANSWERED
1. ~~Does it support voice cloning from audio samples?~~ **YES** - short samples work
2. ~~What preset voices are available?~~ **N/A** - cloning is the path
3. ~~Can it handle rhythmic/musical delivery?~~ **YES** - via prompt (artist refs, beat hints, cadence)
4. ~~What emotion/style controls exist?~~ **Prompt-based**
5. ~~What's the audio output format?~~ **Real-time or pre-rendered**
6. Rate limits during hackathon? **TBD - test early**

### Still Open
7. Exact Grok Video API capabilities and input format?
8. Is there a Grok audio/music generation model for beats?
9. Can we batch video generation or need frame-by-frame?
10. Team member responsibilities split?



### TO TEST
##### 1. Build the image
docker build . --tag grok-rap-battle --progress=plain

##### 2. Run with your .env.local file
docker run -d \
  --name grok-rap-battle \
  -p 7860:7860 \
  --env-file .env.local \
  grok-rap-battle

##### 3. Check logs
docker logs -f grok-rap-battle

##### 4. Open in browser
open http://localhost:7860
