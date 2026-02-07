/**
 * Mesa Redonda AI - Multi-Agent Frontend
 * Handles video routing for multiple avatars
 */

// DOM Elements
const connectBtn = document.getElementById('connect-btn');
const disconnectBtn = document.getElementById('disconnect-btn');
const micBtn = document.getElementById('mic-btn');
const statusDiv = document.getElementById('status');
const visualizerCanvas = document.getElementById('visualizer');

// Avatar containers map
const avatarContainers = {
    'cosmo': document.getElementById('video-container-cosmo'),
    'maya': document.getElementById('video-container-maya'),
    'ricardo': document.getElementById('video-container-ricardo'),
    'lucas': document.getElementById('video-container-lucas'),
    'fernanda': document.getElementById('video-container-fernanda')
};

// Avatar cards for status updates
const avatarCards = {
    'cosmo': document.getElementById('avatar-cosmo'),
    'maya': document.getElementById('avatar-maya'),
    'ricardo': document.getElementById('avatar-ricardo'),
    'lucas': document.getElementById('avatar-lucas'),
    'fernanda': document.getElementById('avatar-fernanda')
};

let room;
let isMicEnabled = true;

connectBtn.addEventListener('click', connectToRoom);
disconnectBtn.addEventListener('click', disconnectFromRoom);
micBtn.addEventListener('click', toggleMic);

/**
 * Map participant identity to avatar name
 */
function getAvatarName(participantIdentity) {
    const identity = participantIdentity.toLowerCase();

    // Check for specialist identifiers
    if (identity.includes('maya') || identity.includes('marketing')) return 'maya';
    if (identity.includes('ricardo') || identity.includes('finance')) return 'ricardo';
    if (identity.includes('lucas') || identity.includes('product')) return 'lucas';
    if (identity.includes('fernanda') || identity.includes('legal')) return 'fernanda';

    // Default to Cosmo (host)
    return 'cosmo';
}

async function connectToRoom() {
    try {
        updateStatus('CONECTANDO...', 'connecting');

        const response = await fetch('/token');
        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        room = new LivekitClient.Room({
            adaptiveStream: true,
            dynacast: true,
        });

        // Handle Track Subscriptions
        room.on(LivekitClient.RoomEvent.TrackSubscribed, handleTrackSubscribed);
        room.on(LivekitClient.RoomEvent.TrackUnsubscribed, handleTrackUnsubscribed);
        room.on(LivekitClient.RoomEvent.Disconnected, handleDisconnect);
        room.on(LivekitClient.RoomEvent.ParticipantConnected, handleParticipantConnected);
        room.on(LivekitClient.RoomEvent.ParticipantDisconnected, handleParticipantDisconnected);

        await room.connect(data.url, data.token);
        console.log('[ROOM] Connected to room:', room.name);

        // Enable microphone
        try {
            await room.localParticipant.setMicrophoneEnabled(true);
            console.log('[AUDIO] Microphone enabled');
        } catch (error) {
            console.error('[AUDIO ERROR]', error);
            updateStatus('ERRO: ' + error.message, 'error');
            throw error;
        }

        updateStatus('CONECTADO', 'connected');
        showConnectedState();
        setupVisualizer();

    } catch (error) {
        console.error('Error connecting:', error);
        updateStatus('ERRO: ' + error.message, 'error');
    }
}

function handleParticipantConnected(participant) {
    console.log('[PARTICIPANT] Connected:', participant.identity);
    const avatarName = getAvatarName(participant.identity);
    updateAvatarStatus(avatarName, 'online');
}

function handleParticipantDisconnected(participant) {
    console.log('[PARTICIPANT] Disconnected:', participant.identity);
    const avatarName = getAvatarName(participant.identity);
    updateAvatarStatus(avatarName, 'offline');
    restorePlaceholder(avatarName);
}

function handleTrackSubscribed(track, publication, participant) {
    console.log('[TRACK] Subscribed:', {
        kind: track.kind,
        participant: participant.identity
    });

    const avatarName = getAvatarName(participant.identity);
    const container = avatarContainers[avatarName];

    if (!container) {
        console.warn('[TRACK] No container for avatar:', avatarName);
        return;
    }

    if (track.kind === LivekitClient.Track.Kind.Video) {
        console.log('[VIDEO] Attaching to:', avatarName);

        const videoElement = track.attach();
        videoElement.style.width = '100%';
        videoElement.style.height = '100%';
        videoElement.style.objectFit = 'cover';
        videoElement.setAttribute('playsinline', '');
        videoElement.setAttribute('autoplay', '');
        videoElement.muted = true;

        container.innerHTML = '';
        container.appendChild(videoElement);

        videoElement.play().then(() => {
            console.log('[VIDEO] Playing:', avatarName);
        }).catch(e => {
            console.error('[VIDEO ERROR]', e);
        });

        // Update avatar status
        updateAvatarStatus(avatarName, 'online');

        // Mark card as active
        if (avatarCards[avatarName]) {
            avatarCards[avatarName].classList.add('active');
        }

        // Update main status for host
        if (avatarName === 'cosmo') {
            updateStatus('MENTOR CONECTADO', 'connected');
        }

    } else if (track.kind === LivekitClient.Track.Kind.Audio) {
        console.log('[AUDIO] Attaching from:', avatarName);
        const element = track.attach();
        element.id = `audio-${avatarName}`;
        document.body.appendChild(element);
        element.play().catch(e => console.error('[AUDIO ERROR]', e));
    }
}

function handleTrackUnsubscribed(track, publication, participant) {
    console.log('[TRACK] Unsubscribed:', track.kind, participant.identity);
    track.detach().forEach(element => element.remove());

    const avatarName = getAvatarName(participant.identity);

    if (track.kind === LivekitClient.Track.Kind.Video) {
        restorePlaceholder(avatarName);
        if (avatarCards[avatarName]) {
            avatarCards[avatarName].classList.remove('active');
        }
    }
}

function updateAvatarStatus(avatarName, status) {
    const card = avatarCards[avatarName];
    if (!card) return;

    const indicator = card.querySelector('.status-indicator');
    const statusText = card.querySelector('.avatar-status span:last-child');

    if (indicator) {
        indicator.className = 'status-indicator ' + status;
    }

    if (statusText) {
        if (status === 'online') {
            statusText.textContent = 'Online';
        } else if (status === 'speaking') {
            statusText.textContent = 'Falando...';
        } else {
            statusText.textContent = avatarName === 'cosmo' ? 'Offline' : 'Disponível';
        }
    }
}

function restorePlaceholder(avatarName) {
    const container = avatarContainers[avatarName];
    if (!container) return;

    const icons = {
        cosmo: '🎯',
        maya: '📈',
        ricardo: '💰',
        lucas: '💡',
        fernanda: '⚖️'
    };

    const isHost = avatarName === 'cosmo';
    const scannerLine = isHost ? '<div class="scanner-line"></div>' : '';
    const waitText = isHost ? '<p>AGUARDANDO...</p>' : '';

    container.innerHTML = `
        <div class="placeholder">
            ${scannerLine}
            <div class="avatar-icon">${icons[avatarName] || '👤'}</div>
            ${waitText}
        </div>
    `;

    updateAvatarStatus(avatarName, 'offline');
}

async function disconnectFromRoom() {
    if (room) {
        await room.disconnect();
    }
}

function handleDisconnect() {
    updateStatus('DESCONECTADO', '');
    showDisconnectedState();

    // Restore all placeholders
    Object.keys(avatarContainers).forEach(name => {
        restorePlaceholder(name);
        if (avatarCards[name]) {
            avatarCards[name].classList.remove('active');
        }
    });
}

async function toggleMic() {
    if (!room) return;
    isMicEnabled = !isMicEnabled;
    await room.localParticipant.setMicrophoneEnabled(isMicEnabled);

    const micPath = isMicEnabled ?
        '<path fill="currentColor" d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/><path fill="currentColor" d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>' :
        '<path fill="currentColor" d="M19 11h-1.7c0 .74-.16 1.43-.43 2.05l1.23 1.23c.56-.98.9-2.09.9-3.28zm-4.02.17c0-.06.02-.11.02-.17V5c0-1.66-1.34-3-3-3S9 3.34 9 5v.18l5.98 5.99zM4.27 3L3 4.27l6.01 6.01V11c0 1.66 1.33 3 2.99 3 .22 0 .44-.03.65-.08l2.97 2.97c-.85.35-1.76.56-2.71.56-3.53 0-6.14-2.9-6.68-6.43H4.22c.56 4.3 4.2 7.7 8.52 7.88V21h2v-3.08c.57-.04 1.12-.13 1.63-.26L19.73 21 21 19.73 4.27 3z"/>';

    micBtn.innerHTML = `<svg viewBox="0 0 24 24" width="24" height="24">${micPath}</svg>`;
    micBtn.classList.toggle('disabled', !isMicEnabled);
    micBtn.style.opacity = isMicEnabled ? '1' : '0.5';
}

function setupVisualizer() {
    if (!room || !room.localParticipant) return;

    const publication = room.localParticipant.getTrackPublication(LivekitClient.Track.Source.Microphone);
    const audioTrack = publication ? publication.track : null;

    if (!audioTrack) {
        console.error('[VISUALIZER] No audio track');
        return;
    }

    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;

    const stream = new MediaStream([audioTrack.mediaStreamTrack]);
    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    const canvasCtx = visualizerCanvas.getContext('2d');

    function draw() {
        if (!room || room.state === 'disconnected') return;

        requestAnimationFrame(draw);
        analyser.getByteFrequencyData(dataArray);

        canvasCtx.clearRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);

        // Simple bar visualizer
        const barWidth = visualizerCanvas.width / bufferLength * 2;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
            const barHeight = (dataArray[i] / 255) * visualizerCanvas.height;

            const gradient = canvasCtx.createLinearGradient(0, visualizerCanvas.height, 0, 0);
            gradient.addColorStop(0, '#00f3ff');
            gradient.addColorStop(1, '#bc13fe');

            canvasCtx.fillStyle = gradient;
            canvasCtx.fillRect(x, visualizerCanvas.height - barHeight, barWidth - 1, barHeight);

            x += barWidth;
        }
    }

    draw();
}

function updateStatus(text, type) {
    const statusText = statusDiv.querySelector('.status-text');
    if (statusText) statusText.textContent = text;

    statusDiv.className = 'status-badge';
    if (type === 'connected') {
        statusDiv.classList.add('connected');
    }
}

function showConnectedState() {
    connectBtn.classList.add('hidden');
    disconnectBtn.classList.remove('hidden');
    micBtn.classList.remove('disabled');
}

function showDisconnectedState() {
    connectBtn.classList.remove('hidden');
    disconnectBtn.classList.add('hidden');
    micBtn.classList.add('disabled');
}
