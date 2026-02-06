
const videoContainer = document.getElementById('video-container');
const connectBtn = document.getElementById('connect-btn');
const disconnectBtn = document.getElementById('disconnect-btn');
const micBtn = document.getElementById('mic-btn');
const statusDiv = document.getElementById('status');
const visualizerCanvas = document.getElementById('visualizer');

let room;
let isMicEnabled = true;

connectBtn.addEventListener('click', connectToRoom);
disconnectBtn.addEventListener('click', disconnectFromRoom);
micBtn.addEventListener('click', toggleMic);

async function connectToRoom() {
    try {
        updateStatus('CONNECTING...', 'connecting');

        // Fetch token from local server
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

        await room.connect(data.url, data.token);
        console.log('[AUDIO DEBUG] Connected to room:', room.name);

        // Publish Local Microphone ONLY (not camera)
        console.log('[AUDIO DEBUG] Requesting microphone access...');
        try {
            await room.localParticipant.setMicrophoneEnabled(true);
            console.log('[AUDIO DEBUG] Microphone enabled successfully');
        } catch (error) {
            console.error('[AUDIO ERROR] Failed to enable microphone:', error);
            if (error.name === 'NotAllowedError') {
                updateStatus('ERROR: Permissão de microfone negada', 'error');
                alert('Por favor, permita o acesso ao microfone nas configurações do navegador.');
            } else if (error.name === 'NotFoundError') {
                updateStatus('ERROR: Microfone não encontrado', 'error');
                alert('Nenhum microfone foi encontrado. Verifique se está conectado.');
            } else {
                updateStatus('ERROR: ' + error.message, 'error');
            }
            throw error; // Re-throw to stop connection flow
        }

        // Log all local tracks
        console.log('[AUDIO DEBUG] Local tracks:', Array.from(room.localParticipant.trackPublications.values()).map(p => ({
            source: p.source,
            kind: p.kind,
            trackSid: p.trackSid,
            isMuted: p.isMuted,
            enabled: p.track ? p.track.mediaStreamTrack.enabled : 'N/A',
            readyState: p.track ? p.track.mediaStreamTrack.readyState : 'N/A'
        })));

        updateStatus('CONNECTED', 'connected');
        showConnectedState();

        // Start Visualizer
        setupVisualizer();

    } catch (error) {
        console.error('Error connecting:', error);
        updateStatus('ERROR: ' + error.message, 'error');
    }
}

function setupVisualizer() {
    console.log('[VISUALIZER DEBUG] Setting up visualizer...');
    if (!room || !room.localParticipant) {
        console.error('[VISUALIZER DEBUG] Room or localParticipant not available');
        return;
    }

    // Correct way to get local track publication
    console.log('[VISUALIZER DEBUG] Getting microphone track publication...');
    const publication = room.localParticipant.getTrackPublication(LivekitClient.Track.Source.Microphone);
    console.log('[VISUALIZER DEBUG] Publication:', publication);
    const audioTrack = publication ? publication.track : null;
    console.log('[VISUALIZER DEBUG] Audio track:', audioTrack);

    if (!audioTrack) {
        console.error('[VISUALIZER DEBUG] No local audio track found for visualizer');
        console.log('[VISUALIZER DEBUG] Available publications:', Array.from(room.localParticipant.trackPublications.values()));
        return;
    }

    console.log('[VISUALIZER DEBUG] Audio track mediaStreamTrack:', audioTrack.mediaStreamTrack);

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

        const centerX = visualizerCanvas.width / 2;
        const centerY = visualizerCanvas.height / 2;
        const baseRadius = 60;

        // Draw glowing outer ring based on volume
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
            sum += dataArray[i];
        }
        const average = sum / bufferLength;
        const pulse = average * 0.5;

        canvasCtx.beginPath();
        canvasCtx.arc(centerX, centerY, baseRadius + pulse, 0, 2 * Math.PI);
        canvasCtx.strokeStyle = 'rgba(204, 255, 0, 0.5)';
        canvasCtx.lineWidth = 2;
        canvasCtx.stroke();

        // Draw frequency bars in a circle
        const barCount = 60;
        for (let i = 0; i < barCount; i++) {
            const angle = (i / barCount) * Math.PI * 2;
            const value = dataArray[i % bufferLength];
            const barHeight = (value / 255) * 40;

            const x1 = centerX + Math.cos(angle) * baseRadius;
            const y1 = centerY + Math.sin(angle) * baseRadius;
            const x2 = centerX + Math.cos(angle) * (baseRadius + barHeight);
            const y2 = centerY + Math.sin(angle) * (baseRadius + barHeight);

            canvasCtx.beginPath();
            canvasCtx.moveTo(x1, y1);
            canvasCtx.lineTo(x2, y2);
            canvasCtx.strokeStyle = '#ccff00';
            canvasCtx.lineWidth = 2;
            canvasCtx.stroke();
        }
    }

    draw();
}

function handleTrackSubscribed(track, publication, participant) {
    console.log('[TRACK DEBUG] Track subscribed:', {
        trackSid: track.sid,
        trackKind: track.kind,
        participantIdentity: participant.identity,
        participantKind: participant.kind
    });

    if (track.kind === LivekitClient.Track.Kind.Video) {
        console.log('[TRACK DEBUG] Attaching video track from:', participant.identity);
        const videoElement = track.attach();
        videoElement.style.width = '100%';
        videoElement.style.height = '100%';
        videoElement.style.objectFit = 'cover';
        videoContainer.innerHTML = '';
        videoContainer.appendChild(videoElement);
        updateStatus('AGENT CONNECTED', 'connected');
    } else if (track.kind === LivekitClient.Track.Kind.Audio) {
        console.log('[TRACK DEBUG] Audio track subscribed from:', participant.identity);
        console.log("Attaching Audio Track...");
        // Play audio
        const element = track.attach();
        document.body.appendChild(element);
    }
}

function handleTrackUnsubscribed(track, publication, participant) {
    console.log("Track unsubscribed:", track.kind);
    track.detach().forEach(element => element.remove());
    if (track.kind === LivekitClient.Track.Kind.Video) {
        videoContainer.innerHTML = `
            <div class="placeholder">
                <div class="scanner"></div>
                <p>WAITING FOR AGENT</p>
            </div>
        `;
    }
}

async function disconnectFromRoom() {
    if (room) {
        await room.disconnect();
    }
}

function handleDisconnect() {
    updateStatus('DISCONNECTED', '');
    showDisconnectedState();
    videoContainer.innerHTML = `
                    <div class="placeholder">
                        <div class="scanner"></div>
                        <p>WAITING FOR AGENT</p>
                    </div>
                `;
}

async function toggleMic() {
    if (!room) return;
    isMicEnabled = !isMicEnabled;
    await room.localParticipant.setMicrophoneEnabled(isMicEnabled);
    micBtn.innerHTML = isMicEnabled ?
        '<svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/><path fill="currentColor" d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/></svg>' :
        '<svg viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M19 11h-1.7c0 .74-.16 1.43-.43 2.05l1.23 1.23c.56-.98.9-2.09.9-3.28zm-4.02.17c0-.06.02-.11.02-.17V5c0-1.66-1.34-3-3-3S9 3.34 9 5v.18l5.98 5.99zM4.27 3L3 4.27l6.01 6.01V11c0 1.66 1.33 3 2.99 3 .22 0 .44-.03.65-.08l2.97 2.97c-.85.35-1.76.56-2.71.56-3.53 0-6.14-2.9-6.68-6.43H4.22c.56 4.3 4.2 7.7 8.52 7.88V21h2v-3.08c.57-.04 1.12-.13 1.63-.26L19.73 21 21 19.73 4.27 3z"/></svg>';
    micBtn.style.opacity = isMicEnabled ? '1' : '0.5';
}

function updateStatus(text, className) {
    statusDiv.textContent = text;
    statusDiv.className = 'status ' + className;
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
