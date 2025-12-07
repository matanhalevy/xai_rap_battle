/**
 * GROK RAP BATTLE - 8-Bit Arcade Frontend
 * Main application JavaScript
 */

// ============================================
// STATE MANAGEMENT
// ============================================
const state = {
    fighterA: {
        name: '',
        image: null,
        imagePreview: null,
        description: '',
        style: 'UK Grime 1 (Stormzy)',
        customVoice: null,
        lyrics: '',
        twitter: ''
    },
    fighterB: {
        name: '',
        image: null,
        imagePreview: null,
        description: '',
        style: 'West Coast (Kendrick)',
        customVoice: null,
        lyrics: '',
        twitter: ''
    },
    battle: {
        videoStyle: 'Photorealistic',
        location: 'underground hip-hop club',
        beatStyle: 'trap',
        testMode: true,
        audioOnly: true
    },
    detectedBpm: null,
    currentBattle: {
        id: null,
        eventSource: null
    }
};

// ============================================
// DOM ELEMENTS
// ============================================
const elements = {
    // Fighter A
    nameA: document.getElementById('name-a'),
    imageA: document.getElementById('image-a'),
    portraitA: document.getElementById('portrait-a'),
    portraitImgA: document.getElementById('portrait-img-a'),
    descA: document.getElementById('desc-a'),
    styleA: document.getElementById('style-a'),
    voiceA: document.getElementById('voice-a'),
    voiceStatusA: document.getElementById('voice-status-a'),
    lyricsA: document.getElementById('lyrics-a'),
    healthA: document.getElementById('health-a'),
    twitterA: document.getElementById('twitter-a'),

    // Fighter B
    nameB: document.getElementById('name-b'),
    imageB: document.getElementById('image-b'),
    portraitB: document.getElementById('portrait-b'),
    portraitImgB: document.getElementById('portrait-img-b'),
    descB: document.getElementById('desc-b'),
    styleB: document.getElementById('style-b'),
    voiceB: document.getElementById('voice-b'),
    voiceStatusB: document.getElementById('voice-status-b'),
    lyricsB: document.getElementById('lyrics-b'),
    healthB: document.getElementById('health-b'),
    twitterB: document.getElementById('twitter-b'),

    // Battle config
    videoStyle: document.getElementById('video-style'),
    location: document.getElementById('location'),
    beatStyle: document.getElementById('beat-style'),
    bpm: document.getElementById('bpm'),
    bpmValue: document.getElementById('bpm-value'),
    testMode: document.getElementById('test-mode'),
    audioOnly: document.getElementById('audio-only'),

    // Fight button
    fightBtn: document.getElementById('fight-btn'),

    // Progress modal
    progressModal: document.getElementById('progress-modal'),
    currentStage: document.getElementById('current-stage'),
    progressFill: document.getElementById('progress-fill'),
    progressPercent: document.getElementById('progress-percent'),
    statusText: document.getElementById('status-text'),

    // Result modal
    resultModal: document.getElementById('result-modal'),
    resultVideo: document.getElementById('result-video'),
    detectedBpmDisplay: document.getElementById('detected-bpm-display'),
    downloadBtn: document.getElementById('download-btn'),
    newBattleBtn: document.getElementById('new-battle-btn'),
    scoreValue: document.getElementById('score-value'),

    // Error modal
    errorModal: document.getElementById('error-modal'),
    errorMessage: document.getElementById('error-message'),
    errorCloseBtn: document.getElementById('error-close-btn')
};

// Stage elements (full pipeline with video)
const stages = {
    parsing: document.getElementById('stage-parsing'),
    voice_a: document.getElementById('stage-voice_a'),
    voice_b: document.getElementById('stage-voice_b'),
    bpm_detect: document.getElementById('stage-bpm_detect'),
    beat_gen: document.getElementById('stage-beat_gen'),
    mixing: document.getElementById('stage-mixing'),
    storyboard: document.getElementById('stage-storyboard'),
    video: document.getElementById('stage-video'),
    lipsync: document.getElementById('stage-lipsync'),
    compose: document.getElementById('stage-compose')
};

// ============================================
// INITIALIZATION
// ============================================
function init() {
    setupEventListeners();
    initDropdowns();
    loadSavedState();
    updateHealthBars();
    playStartupSound();
}

function setupEventListeners() {
    // Fighter A inputs
    elements.nameA.addEventListener('input', (e) => {
        state.fighterA.name = e.target.value;
        saveState();
    });

    elements.imageA.addEventListener('change', (e) => {
        handleImageUpload(e, 'A');
    });

    elements.descA.addEventListener('input', (e) => {
        state.fighterA.description = e.target.value;
        saveState();
    });

    elements.styleA.addEventListener('change', (e) => {
        state.fighterA.style = e.target.value;
        saveState();
    });

    elements.voiceA.addEventListener('change', (e) => {
        if (e.target.files[0]) {
            state.fighterA.customVoice = e.target.files[0];
            updateVoiceStatus('A', e.target.files[0].name);
            playSelectSound();
        }
    });

    elements.lyricsA.addEventListener('input', (e) => {
        state.fighterA.lyrics = e.target.value;
        saveState();
    });

    elements.twitterA.addEventListener('input', (e) => {
        state.fighterA.twitter = e.target.value;
        saveState();
    });

    // Fighter B inputs
    elements.nameB.addEventListener('input', (e) => {
        state.fighterB.name = e.target.value;
        saveState();
    });

    elements.imageB.addEventListener('change', (e) => {
        handleImageUpload(e, 'B');
    });

    elements.descB.addEventListener('input', (e) => {
        state.fighterB.description = e.target.value;
        saveState();
    });

    elements.styleB.addEventListener('change', (e) => {
        state.fighterB.style = e.target.value;
        saveState();
    });

    elements.voiceB.addEventListener('change', (e) => {
        if (e.target.files[0]) {
            state.fighterB.customVoice = e.target.files[0];
            updateVoiceStatus('B', e.target.files[0].name);
            playSelectSound();
        }
    });

    elements.lyricsB.addEventListener('input', (e) => {
        state.fighterB.lyrics = e.target.value;
        saveState();
    });

    elements.twitterB.addEventListener('input', (e) => {
        state.fighterB.twitter = e.target.value;
        saveState();
    });

    // Battle config inputs
    elements.videoStyle.addEventListener('change', (e) => {
        state.battle.videoStyle = e.target.value;
        saveState();
    });

    elements.location.addEventListener('input', (e) => {
        state.battle.location = e.target.value;
        saveState();
    });

    elements.beatStyle.addEventListener('change', (e) => {
        state.battle.beatStyle = e.target.value;
        saveState();
    });

    elements.testMode.addEventListener('change', (e) => {
        state.battle.testMode = e.target.checked;
        saveState();
    });

    elements.audioOnly.addEventListener('change', (e) => {
        state.battle.audioOnly = e.target.checked;
        saveState();
    });

    // Fight button
    elements.fightBtn.addEventListener('click', startBattle);

    // Modal buttons
    elements.newBattleBtn.addEventListener('click', () => {
        hideModal('result');
        resetBattle();
    });

    elements.errorCloseBtn.addEventListener('click', () => {
        hideModal('error');
    });

    // Close modals on backdrop click
    document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', (e) => {
            const modal = e.target.closest('.modal');
            if (modal.id === 'error-modal') {
                hideModal('error');
            }
        });
    });
}

// ============================================
// IMAGE HANDLING
// ============================================
function handleImageUpload(event, fighter) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        const imageData = e.target.result;

        if (fighter === 'A') {
            state.fighterA.image = file;
            state.fighterA.imagePreview = imageData;
            updatePortrait('A', imageData);
        } else {
            state.fighterB.image = file;
            state.fighterB.imagePreview = imageData;
            updatePortrait('B', imageData);
        }

        playSelectSound();
        saveState();
    };
    reader.readAsDataURL(file);
}

function updatePortrait(fighter, imageData) {
    const portrait = fighter === 'A' ? elements.portraitA : elements.portraitB;
    const img = fighter === 'A' ? elements.portraitImgA : elements.portraitImgB;

    // Hide placeholder, show image
    const placeholder = portrait.querySelector('.portrait-placeholder');
    if (placeholder) {
        placeholder.style.display = 'none';
    }

    img.src = imageData;
    img.style.display = 'block';

    // Add selection animation
    portrait.closest('.portrait-frame').classList.add('selected');
}

// ============================================
// STATE PERSISTENCE
// ============================================
function saveState() {
    const saveData = {
        fighterA: {
            name: state.fighterA.name,
            description: state.fighterA.description,
            style: state.fighterA.style,
            lyrics: state.fighterA.lyrics,
            imagePreview: state.fighterA.imagePreview,
            twitter: state.fighterA.twitter
        },
        fighterB: {
            name: state.fighterB.name,
            description: state.fighterB.description,
            style: state.fighterB.style,
            lyrics: state.fighterB.lyrics,
            imagePreview: state.fighterB.imagePreview,
            twitter: state.fighterB.twitter
        },
        battle: state.battle
    };
    localStorage.setItem('grokRapBattle', JSON.stringify(saveData));
}

function loadSavedState() {
    const saved = localStorage.getItem('grokRapBattle');
    if (!saved) return;

    try {
        const data = JSON.parse(saved);

        // Restore Fighter A
        if (data.fighterA) {
            state.fighterA.name = data.fighterA.name || '';
            state.fighterA.description = data.fighterA.description || '';
            state.fighterA.style = data.fighterA.style || 'UK Grime 1 (Stormzy)';
            state.fighterA.lyrics = data.fighterA.lyrics || '';
            state.fighterA.imagePreview = data.fighterA.imagePreview || null;
            state.fighterA.twitter = data.fighterA.twitter || '';

            elements.nameA.value = state.fighterA.name;
            elements.descA.value = state.fighterA.description;
            elements.styleA.value = state.fighterA.style;
            elements.lyricsA.value = state.fighterA.lyrics;
            elements.twitterA.value = state.fighterA.twitter;

            if (state.fighterA.imagePreview) {
                updatePortrait('A', state.fighterA.imagePreview);
            }
        }

        // Restore Fighter B
        if (data.fighterB) {
            state.fighterB.name = data.fighterB.name || '';
            state.fighterB.description = data.fighterB.description || '';
            state.fighterB.style = data.fighterB.style || 'West Coast (Kendrick)';
            state.fighterB.lyrics = data.fighterB.lyrics || '';
            state.fighterB.imagePreview = data.fighterB.imagePreview || null;
            state.fighterB.twitter = data.fighterB.twitter || '';

            elements.nameB.value = state.fighterB.name;
            elements.descB.value = state.fighterB.description;
            elements.styleB.value = state.fighterB.style;
            elements.lyricsB.value = state.fighterB.lyrics;
            elements.twitterB.value = state.fighterB.twitter;

            if (state.fighterB.imagePreview) {
                updatePortrait('B', state.fighterB.imagePreview);
            }
        }

        // Restore Battle config
        if (data.battle) {
            state.battle = { ...state.battle, ...data.battle };
            elements.videoStyle.value = state.battle.videoStyle;
            elements.location.value = state.battle.location;
            elements.beatStyle.value = state.battle.beatStyle;
            elements.testMode.checked = state.battle.testMode;
            elements.audioOnly.checked = state.battle.audioOnly;
        }
    } catch (e) {
        console.error('Failed to load saved state:', e);
    }
}

// ============================================
// BATTLE API
// ============================================
async function startBattle() {
    // Validate inputs
    const validation = validateBattleInputs();
    if (!validation.valid) {
        showError(validation.message);
        return;
    }

    // Disable fight button
    elements.fightBtn.disabled = true;
    playFightSound();

    // Show progress modal
    showModal('progress');
    resetProgressUI();

    try {
        // Auto-generate lyrics if empty
        const needsLyricsA = !state.fighterA.lyrics.trim();
        const needsLyricsB = !state.fighterB.lyrics.trim();

        if (needsLyricsA || needsLyricsB) {
            elements.statusText.textContent = 'GENERATING LYRICS...';
            elements.progressFill.style.width = '5%';

            const generated = await generateLyrics();

            if (needsLyricsA) {
                state.fighterA.lyrics = generated.fighter_a_lyrics;
                elements.lyricsA.value = generated.fighter_a_lyrics;
            }
            if (needsLyricsB) {
                state.fighterB.lyrics = generated.fighter_b_lyrics;
                elements.lyricsB.value = generated.fighter_b_lyrics;
            }
            saveState();
        }

        // Build form data
        const formData = new FormData();

        // Battle config (BPM auto-detected from rap audio)
        formData.append('video_style', state.battle.videoStyle);
        formData.append('location', state.battle.location);
        formData.append('time_period', 'present day');  // Default time period
        formData.append('beat_style', state.battle.beatStyle);
        formData.append('test_mode', state.battle.testMode);
        formData.append('audio_only', state.battle.audioOnly);

        // Fighter A
        formData.append('fighter_a_name', state.fighterA.name);
        formData.append('fighter_a_description', state.fighterA.description);
        formData.append('fighter_a_style', state.fighterA.style);
        formData.append('fighter_a_lyrics', state.fighterA.lyrics);
        formData.append('fighter_a_twitter', state.fighterA.twitter);

        if (state.fighterA.image) {
            formData.append('fighter_a_image', state.fighterA.image);
        }
        if (state.fighterA.customVoice) {
            formData.append('fighter_a_voice', state.fighterA.customVoice);
        }

        // Fighter B
        formData.append('fighter_b_name', state.fighterB.name);
        formData.append('fighter_b_description', state.fighterB.description);
        formData.append('fighter_b_style', state.fighterB.style);
        formData.append('fighter_b_lyrics', state.fighterB.lyrics);
        formData.append('fighter_b_twitter', state.fighterB.twitter);

        if (state.fighterB.image) {
            formData.append('fighter_b_image', state.fighterB.image);
        }
        if (state.fighterB.customVoice) {
            formData.append('fighter_b_voice', state.fighterB.customVoice);
        }

        // Start battle
        const response = await fetch('/api/battle/start', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            // Handle FastAPI validation errors (detail can be string or array)
            let errorMsg = 'Failed to start battle';
            if (typeof error.detail === 'string') {
                errorMsg = error.detail;
            } else if (Array.isArray(error.detail)) {
                errorMsg = error.detail.map(e => e.msg || e.message || JSON.stringify(e)).join(', ');
            }
            throw new Error(errorMsg);
        }

        const data = await response.json();
        state.currentBattle.id = data.battle_id;

        // Connect to SSE for progress
        connectProgressStream(data.battle_id);

    } catch (error) {
        console.error('Battle start error:', error);
        hideModal('progress');
        showError(error.message);
        elements.fightBtn.disabled = false;
    }
}

function validateBattleInputs() {
    if (!state.fighterA.name.trim()) {
        return { valid: false, message: 'PLAYER 1 NEEDS A NAME!' };
    }
    if (!state.fighterB.name.trim()) {
        return { valid: false, message: 'PLAYER 2 NEEDS A NAME!' };
    }
    // Lyrics are optional - auto-generated if empty
    if (!state.battle.location.trim()) {
        return { valid: false, message: 'SET A LOCATION!' };
    }
    return { valid: true };
}

async function generateLyrics() {
    const formData = new FormData();
    formData.append('fighter_a_name', state.fighterA.name);
    formData.append('fighter_b_name', state.fighterB.name);
    formData.append('theme', state.battle.location);  // Use location as theme for lyrics
    formData.append('fighter_a_twitter', state.fighterA.twitter);
    formData.append('fighter_b_twitter', state.fighterB.twitter);
    formData.append('fighter_a_description', state.fighterA.description);
    formData.append('fighter_b_description', state.fighterB.description);
    formData.append('fighter_a_style', state.fighterA.style);
    formData.append('fighter_b_style', state.fighterB.style);
    formData.append('beat_style', state.battle.beatStyle);
    formData.append('beat_bpm', 140);

    const response = await fetch('/api/lyrics/generate', {
        method: 'POST',
        body: formData
    });

    if (!response.ok) {
        const error = await response.json();
        let errorMsg = 'Failed to generate lyrics';
        if (typeof error.detail === 'string') {
            errorMsg = error.detail;
        } else if (Array.isArray(error.detail)) {
            errorMsg = error.detail.map(e => e.msg || e.message || JSON.stringify(e)).join(', ');
        }
        throw new Error(errorMsg);
    }

    return await response.json();
}

// ============================================
// SSE PROGRESS STREAM
// ============================================
function connectProgressStream(battleId) {
    // Close existing connection if any
    if (state.currentBattle.eventSource) {
        state.currentBattle.eventSource.close();
    }

    const eventSource = new EventSource(`/api/battle/${battleId}/status`);
    state.currentBattle.eventSource = eventSource;

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleProgressUpdate(data);
        } catch (e) {
            console.error('Failed to parse progress data:', e);
        }
    };

    eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        eventSource.close();

        // Check if battle completed successfully
        if (!document.getElementById('result-modal').classList.contains('active')) {
            hideModal('progress');
            showError('CONNECTION LOST. PLEASE TRY AGAIN.');
            elements.fightBtn.disabled = false;
        }
    };
}

function handleProgressUpdate(data) {
    // Update progress bar
    if (data.progress !== undefined) {
        elements.progressFill.style.width = `${data.progress}%`;
        elements.progressPercent.textContent = `${Math.round(data.progress)}%`;
    }

    // Update status text
    if (data.message) {
        elements.statusText.textContent = data.message.toUpperCase();
    }

    // Update stage indicators
    if (data.stage) {
        updateStageUI(data.stage);
    }

    // Store detected BPM
    if (data.detected_bpm) {
        state.detectedBpm = data.detected_bpm;
    }

    // Handle completion
    if (data.status === 'complete') {
        handleBattleComplete(data);
    }

    // Handle error
    if (data.status === 'failed') {
        handleBattleError(data);
    }

    // Update health bars based on progress (visual flair)
    updateHealthBars(data.progress);
}

function updateStageUI(currentStage) {
    const stageOrder = ['parsing', 'voice_a', 'voice_b', 'bpm_detect', 'beat_gen', 'mixing'];
    const currentIndex = stageOrder.indexOf(currentStage);

    stageOrder.forEach((stage, index) => {
        const stageEl = stages[stage];
        if (!stageEl) return;

        stageEl.classList.remove('active', 'complete');

        if (index < currentIndex) {
            stageEl.classList.add('complete');
        } else if (index === currentIndex) {
            stageEl.classList.add('active');
        }
    });

    // Update round number display
    elements.currentStage.textContent = currentIndex + 1;
}

function resetProgressUI() {
    elements.progressFill.style.width = '0%';
    elements.progressPercent.textContent = '0%';
    elements.statusText.textContent = 'INITIALIZING...';
    elements.currentStage.textContent = '1';

    Object.values(stages).forEach(stage => {
        if (stage) {
            stage.classList.remove('active', 'complete');
        }
    });
}

// ============================================
// BATTLE COMPLETION
// ============================================
function handleBattleComplete(data) {
    // Close SSE connection
    if (state.currentBattle.eventSource) {
        state.currentBattle.eventSource.close();
    }

    // Hide progress, show result
    hideModal('progress');
    playVictorySound();

    // Set video source (or audio if video not available)
    if (data.video_url) {
        elements.resultVideo.src = data.video_url;
        elements.downloadBtn.href = data.video_url;
    } else if (data.audio_url) {
        // Fallback to audio if video generation failed
        elements.resultVideo.src = data.audio_url;
        elements.downloadBtn.href = data.audio_url;
    }

    // Display detected BPM
    if (data.detected_bpm || state.detectedBpm) {
        elements.detectedBpmDisplay.textContent = data.detected_bpm || state.detectedBpm;
    }

    // Generate random high score for fun
    const score = Math.floor(Math.random() * 900000) + 100000;
    elements.scoreValue.textContent = score.toString();

    showModal('result');
    elements.fightBtn.disabled = false;
}

function handleBattleError(data) {
    // Close SSE connection
    if (state.currentBattle.eventSource) {
        state.currentBattle.eventSource.close();
    }

    hideModal('progress');
    showError(data.message || 'BATTLE FAILED. TRY AGAIN.');
    elements.fightBtn.disabled = false;
}

function resetBattle() {
    // Reset health bars
    elements.healthA.style.width = '100%';
    elements.healthB.style.width = '100%';

    // Reset current battle state
    state.currentBattle.id = null;
    if (state.currentBattle.eventSource) {
        state.currentBattle.eventSource.close();
        state.currentBattle.eventSource = null;
    }
}

// ============================================
// HEALTH BAR ANIMATION
// ============================================
function updateHealthBars(progress = 100) {
    // Simulate battle damage based on progress
    // Player 1 takes "damage" in first half, Player 2 in second half
    const p1Health = progress < 50 ? 100 - progress : 50;
    const p2Health = progress >= 50 ? 100 - (progress - 50) : 100;

    elements.healthA.style.width = `${Math.max(20, p1Health)}%`;
    elements.healthB.style.width = `${Math.max(20, p2Health)}%`;
}

// ============================================
// MODAL MANAGEMENT
// ============================================
function showModal(type) {
    const modal = type === 'progress' ? elements.progressModal :
                  type === 'result' ? elements.resultModal :
                  elements.errorModal;
    modal.classList.add('active');
}

function hideModal(type) {
    const modal = type === 'progress' ? elements.progressModal :
                  type === 'result' ? elements.resultModal :
                  elements.errorModal;
    modal.classList.remove('active');
}

function showError(message) {
    elements.errorMessage.textContent = message;
    showModal('error');
    playErrorSound();
}

// ============================================
// SOUND EFFECTS (8-bit style)
// ============================================
const AudioContext = window.AudioContext || window.webkitAudioContext;
let audioCtx = null;

function getAudioContext() {
    if (!audioCtx) {
        audioCtx = new AudioContext();
    }
    return audioCtx;
}

function playTone(frequency, duration, type = 'square') {
    try {
        const ctx = getAudioContext();
        const oscillator = ctx.createOscillator();
        const gainNode = ctx.createGain();

        oscillator.type = type;
        oscillator.frequency.setValueAtTime(frequency, ctx.currentTime);

        gainNode.gain.setValueAtTime(0.1, ctx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration);

        oscillator.connect(gainNode);
        gainNode.connect(ctx.destination);

        oscillator.start();
        oscillator.stop(ctx.currentTime + duration);
    } catch (e) {
        // Audio not supported
    }
}

function playStartupSound() {
    // Arpeggio on load
    setTimeout(() => playTone(262, 0.1), 0);    // C4
    setTimeout(() => playTone(330, 0.1), 100);  // E4
    setTimeout(() => playTone(392, 0.1), 200);  // G4
    setTimeout(() => playTone(523, 0.2), 300);  // C5
}

function playSelectSound() {
    playTone(440, 0.1);
}

function playFightSound() {
    // Dramatic fight sound
    playTone(200, 0.1);
    setTimeout(() => playTone(250, 0.1), 50);
    setTimeout(() => playTone(300, 0.1), 100);
    setTimeout(() => playTone(400, 0.2), 150);
}

function playVictorySound() {
    // Victory fanfare
    setTimeout(() => playTone(523, 0.15), 0);    // C5
    setTimeout(() => playTone(659, 0.15), 150);  // E5
    setTimeout(() => playTone(784, 0.15), 300);  // G5
    setTimeout(() => playTone(1047, 0.3), 450);  // C6
}

function playErrorSound() {
    playTone(200, 0.2);
    setTimeout(() => playTone(150, 0.3), 150);
}

// ============================================
// CAMERA FUNCTIONALITY
// ============================================
let currentCameraFighter = null;
let cameraStream = null;

const cameraModal = document.getElementById('camera-modal');
const cameraVideo = document.getElementById('camera-video');
const cameraCanvas = document.getElementById('camera-canvas');

async function openCamera(fighter) {
    currentCameraFighter = fighter;

    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'user', width: 640, height: 480 }
        });
        cameraVideo.srcObject = cameraStream;
        cameraModal.classList.add('active');
        playSelectSound();
    } catch (err) {
        console.error('Camera error:', err);
        showError('CAMERA ACCESS DENIED');
    }
}

function closeCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
    cameraVideo.srcObject = null;
    cameraModal.classList.remove('active');
    currentCameraFighter = null;
}

function capturePhoto() {
    if (!cameraStream || !currentCameraFighter) return;

    // Set canvas size to match video
    cameraCanvas.width = cameraVideo.videoWidth;
    cameraCanvas.height = cameraVideo.videoHeight;

    // Draw video frame to canvas (mirror it)
    const ctx = cameraCanvas.getContext('2d');
    ctx.translate(cameraCanvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(cameraVideo, 0, 0);

    // Convert to blob
    cameraCanvas.toBlob((blob) => {
        const file = new File([blob], `portrait_${currentCameraFighter}.png`, { type: 'image/png' });
        const dataUrl = cameraCanvas.toDataURL('image/png');

        // Update state
        if (currentCameraFighter === 'A') {
            state.fighterA.image = file;
            state.fighterA.imagePreview = dataUrl;
            updatePortrait('A', dataUrl);
        } else {
            state.fighterB.image = file;
            state.fighterB.imagePreview = dataUrl;
            updatePortrait('B', dataUrl);
        }

        playSelectSound();
        saveState();
        closeCamera();
    }, 'image/png');
}

// ============================================
// VOICE RECORDING WITH PROMPTS
// ============================================

// Phonetically diverse prompts for voice cloning (Harvard sentences + pangrams)
const VOICE_PROMPTS = [
    "The quick brown fox jumps over the lazy dog.",
    "Pack my box with five dozen liquor jugs.",
    "She sells seashells by the seashore at sunrise.",
    "How vexingly quick daft zebras jump!",
    "The five boxing wizards jump quickly at dawn."
];

// Voice recording state
let voiceRecorder = null;
let voiceAudioChunks = [];
let voiceRecordingFighter = null;
let voiceStream = null;
let currentPromptIndex = 0;
let recordedPrompts = [];
let recordingTimer = null;
let recordingSeconds = 0;

// Voice modal elements
const voiceModal = document.getElementById('voice-modal');
const voicePromptEl = document.getElementById('voice-prompt');
const promptCurrentEl = document.getElementById('prompt-current');
const promptTotalEl = document.getElementById('prompt-total');
const voiceVisualizerEl = document.getElementById('voice-visualizer');
const recordingTimerEl = document.getElementById('recording-timer');
const voiceRecordBtn = document.getElementById('voice-record-btn');
const voiceNextBtn = document.getElementById('voice-next-btn');
const voiceDoneBtn = document.getElementById('voice-done-btn');
const voiceProgressBar = document.getElementById('voice-progress-bar');

// Open voice recording modal (replaces inline toggleRecording)
function toggleRecording(fighter) {
    voiceRecordingFighter = fighter;
    currentPromptIndex = 0;
    recordedPrompts = [];
    recordingSeconds = 0;

    // Reset UI
    promptTotalEl.textContent = VOICE_PROMPTS.length;
    updateVoicePromptUI();
    voiceNextBtn.disabled = true;
    voiceDoneBtn.disabled = true;
    voiceProgressBar.style.width = '0%';
    recordingTimerEl.textContent = '00:00';
    voiceVisualizerEl.classList.remove('active');
    voiceRecordBtn.classList.remove('recording');
    voiceRecordBtn.innerHTML = '<span class="rec-icon"></span> START RECORDING';

    // Show modal
    voiceModal.classList.add('active');
    playSelectSound();
}

function updateVoicePromptUI() {
    promptCurrentEl.textContent = currentPromptIndex + 1;
    voicePromptEl.textContent = `"${VOICE_PROMPTS[currentPromptIndex]}"`;
}

async function toggleVoiceRecording() {
    if (voiceRecorder && voiceRecorder.state === 'recording') {
        // Stop recording
        voiceRecorder.stop();
    } else {
        // Start recording
        try {
            voiceStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            voiceRecorder = new MediaRecorder(voiceStream);
            voiceAudioChunks = [];

            voiceRecorder.ondataavailable = (e) => {
                voiceAudioChunks.push(e.data);
            };

            voiceRecorder.onstop = () => {
                // Save this prompt's audio
                const audioBlob = new Blob(voiceAudioChunks, { type: 'audio/webm' });
                recordedPrompts.push(audioBlob);

                // Stop timer
                clearInterval(recordingTimer);

                // Update UI
                voiceVisualizerEl.classList.remove('active');
                voiceRecordBtn.classList.remove('recording');
                voiceRecordBtn.innerHTML = '<span class="rec-icon"></span> RE-RECORD';

                // Enable next button if not last prompt
                if (currentPromptIndex < VOICE_PROMPTS.length - 1) {
                    voiceNextBtn.disabled = false;
                } else {
                    // Last prompt - enable done button
                    voiceDoneBtn.disabled = false;
                }

                // Update progress
                voiceProgressBar.style.width = `${((currentPromptIndex + 1) / VOICE_PROMPTS.length) * 100}%`;

                playSelectSound();
            };

            // Start recording
            voiceRecorder.start();
            voiceVisualizerEl.classList.add('active');
            voiceRecordBtn.classList.add('recording');
            voiceRecordBtn.innerHTML = '<span class="rec-icon"></span> STOP RECORDING';
            voiceNextBtn.disabled = true;

            // Start timer
            recordingSeconds = 0;
            recordingTimerEl.textContent = '00:00';
            recordingTimer = setInterval(() => {
                recordingSeconds++;
                const mins = Math.floor(recordingSeconds / 60).toString().padStart(2, '0');
                const secs = (recordingSeconds % 60).toString().padStart(2, '0');
                recordingTimerEl.textContent = `${mins}:${secs}`;
            }, 1000);

            playTone(440, 0.1);
        } catch (err) {
            console.error('Microphone error:', err);
            showError('MICROPHONE ACCESS DENIED');
        }
    }
}

function nextVoicePrompt() {
    if (currentPromptIndex < VOICE_PROMPTS.length - 1) {
        currentPromptIndex++;
        updateVoicePromptUI();
        voiceNextBtn.disabled = true;
        voiceRecordBtn.innerHTML = '<span class="rec-icon"></span> START RECORDING';
        recordingTimerEl.textContent = '00:00';
        playSelectSound();
    }
}

async function finishVoiceRecording() {
    // Combine all recorded audio blobs
    const combinedBlob = new Blob(recordedPrompts, { type: 'audio/webm' });
    const file = new File([combinedBlob], `voice_${voiceRecordingFighter}.webm`, { type: 'audio/webm' });

    // Save to state
    if (voiceRecordingFighter === 'A') {
        state.fighterA.customVoice = file;
    } else {
        state.fighterB.customVoice = file;
    }

    // Update voice status
    updateVoiceStatus(voiceRecordingFighter, 'Voice recorded');

    // Clean up
    closeVoiceRecording();
    playVictorySound();
}

function updateVoiceStatus(fighter, text) {
    const statusEl = fighter === 'A' ? elements.voiceStatusA : elements.voiceStatusB;
    statusEl.textContent = text;
    statusEl.classList.add('loaded');
}

function closeVoiceRecording() {
    // Stop any active recording
    if (voiceRecorder && voiceRecorder.state === 'recording') {
        voiceRecorder.stop();
    }

    // Stop stream
    if (voiceStream) {
        voiceStream.getTracks().forEach(track => track.stop());
        voiceStream = null;
    }

    // Clear timer
    if (recordingTimer) {
        clearInterval(recordingTimer);
        recordingTimer = null;
    }

    // Hide modal
    voiceModal.classList.remove('active');
    voiceRecordingFighter = null;
}

// ============================================
// CUSTOM DROPDOWN
// ============================================
async function initDropdowns() {
    // Fetch style presets from API
    await loadStylePresets();

    document.querySelectorAll('.pixel-dropdown').forEach(dropdown => {
        const selected = dropdown.querySelector('.pixel-dropdown-selected');
        const options = dropdown.querySelector('.pixel-dropdown-options');
        const textEl = dropdown.querySelector('.pixel-dropdown-text');

        // Toggle dropdown on click
        selected.addEventListener('click', (e) => {
            e.stopPropagation();

            // Close other dropdowns
            document.querySelectorAll('.pixel-dropdown.open').forEach(d => {
                if (d !== dropdown) d.classList.remove('open');
            });

            dropdown.classList.toggle('open');
            playTone(440, 0.05);
        });

        // Handle option selection
        options.querySelectorAll('.pixel-dropdown-option').forEach(option => {
            option.addEventListener('click', (e) => {
                e.stopPropagation();

                const value = option.dataset.value;
                const text = option.textContent.replace('► ', '');

                // Update selected text
                textEl.textContent = text;
                dropdown.dataset.value = value;

                // Update selected state
                options.querySelectorAll('.pixel-dropdown-option').forEach(o => o.classList.remove('selected'));
                option.classList.add('selected');

                // Update hidden select for form compatibility
                const selectId = dropdown.id.replace('dropdown-', '');
                const hiddenSelect = document.getElementById(selectId);
                if (hiddenSelect) {
                    hiddenSelect.value = value;
                    hiddenSelect.dispatchEvent(new Event('change'));
                }

                // Close dropdown
                dropdown.classList.remove('open');
                playSelectSound();
            });
        });
    });

    // Close dropdowns when clicking outside
    document.addEventListener('click', () => {
        document.querySelectorAll('.pixel-dropdown.open').forEach(d => d.classList.remove('open'));
    });
}

/**
 * Load style presets from API and populate style dropdowns
 */
async function loadStylePresets() {
    try {
        const response = await fetch('/api/presets/styles');
        if (!response.ok) {
            console.error('Failed to fetch style presets');
            return;
        }

        const data = await response.json();
        const presets = data.presets;

        // Populate both style dropdowns
        populateStyleDropdown('dropdown-style-a', 'style-a', presets, state.fighterA.style);
        populateStyleDropdown('dropdown-style-b', 'style-b', presets, state.fighterB.style);
    } catch (error) {
        console.error('Error loading style presets:', error);
    }
}

/**
 * Populate a style dropdown with preset options
 */
function populateStyleDropdown(dropdownId, selectId, presets, defaultValue) {
    const dropdown = document.getElementById(dropdownId);
    const hiddenSelect = document.getElementById(selectId);

    if (!dropdown || !hiddenSelect) return;

    const optionsContainer = dropdown.querySelector('.pixel-dropdown-options');
    const textEl = dropdown.querySelector('.pixel-dropdown-text');

    // Clear existing options
    optionsContainer.innerHTML = '';
    hiddenSelect.innerHTML = '';

    // Find the default preset or use first one
    let defaultPreset = presets.find(p => p.value === defaultValue) || presets[0];

    // Populate options
    presets.forEach(preset => {
        // Create pixel dropdown option
        const option = document.createElement('div');
        option.className = 'pixel-dropdown-option';
        if (preset.value === defaultPreset.value) {
            option.classList.add('selected');
        }
        option.dataset.value = preset.value;
        option.textContent = preset.label;
        optionsContainer.appendChild(option);

        // Create hidden select option
        const selectOption = document.createElement('option');
        selectOption.value = preset.value;
        selectOption.textContent = preset.label;
        if (preset.value === defaultPreset.value) {
            selectOption.selected = true;
        }
        hiddenSelect.appendChild(selectOption);
    });

    // Set default value
    dropdown.dataset.value = defaultPreset.value;
    textEl.textContent = defaultPreset.label;
    hiddenSelect.value = defaultPreset.value;
}

// ============================================
// KEYBOARD SHORTCUTS
// ============================================
document.addEventListener('keydown', (e) => {
    // Enter to fight (when not in textarea/input)
    if (e.key === 'Enter' && !['TEXTAREA', 'INPUT'].includes(e.target.tagName)) {
        if (!elements.fightBtn.disabled) {
            elements.fightBtn.click();
        }
    }

    // Escape to close modals
    if (e.key === 'Escape') {
        if (elements.errorModal.classList.contains('active')) {
            hideModal('error');
        }
    }
});

// ============================================
// INITIALIZE ON DOM LOAD
// ============================================
document.addEventListener('DOMContentLoaded', init);
