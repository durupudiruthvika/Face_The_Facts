// DOM Elements
const videoElement = document.getElementById('inputVideo');
const canvasElement = document.getElementById('outputCanvas');
const canvasCtx = canvasElement.getContext('2d');
const blinkCountDisplay = document.getElementById('blinkCount');
const earDisplay = document.getElementById('earValue');
const statusBadge = document.getElementById('statusBadge');
const stopBtn = document.getElementById('stopBtn');
const loadingMsg = document.getElementById('loadingMessage');

// Debug Elements
const keysDisplay = document.getElementById('keysDisplay'); 
const mouseDisplay = document.getElementById('mouseDisplay');

// Zen Elements
const zenOverlay = document.getElementById('zenOverlay');
const zenText = document.getElementById('zenText');
const zenBtn = document.getElementById('zenBtn');
const closeZenBtn = document.getElementById('closeZenBtn');

// Ergo Elements
const ergoOverlay = document.getElementById('ergoOverlay');
const postureAlert = document.getElementById('postureAlert');
const distanceAlert = document.getElementById('distanceAlert');
const lightAlert = document.getElementById('lightAlert');

// State Variables
let blinkCount = 0;
let isBlinking = false;
let currentEmotion = "Neutral";
let keyPressCount = 0;
let mouseDistance = 0;
let lastMouseX = 0;
let lastMouseY = 0;
let totalEAR = 0;
let earReadings = 0;
let currentEAR = 0;

// --- NOTIFICATION SYSTEM (NEW) ---
let lastNotificationTime = 0;
const NOTIFICATION_COOLDOWN = 15000; // Wait 15 seconds between popups to avoid spam

function requestNotificationPermission() {
    if (!("Notification" in window)) {
        console.log("This browser does not support desktop notification");
    } else {
        Notification.requestPermission();
    }
}

function sendSystemNotification(title, body) {
    // 1. Check Permission
    if (Notification.permission === "granted") {
        // 2. Check Cooldown (Don't spam)
        const now = Date.now();
        if (now - lastNotificationTime > NOTIFICATION_COOLDOWN) {
            // 3. Send Notification
            new Notification(title, {
                body: body,
                icon: '/static/images/logo.png' // Optional: Add a logo path if you have one
            });
            lastNotificationTime = now;
        }
    }
}

// --- THRESHOLDS ---
const EAR_THRESHOLD = (typeof USER_EAR_THRESHOLD !== 'undefined') ? USER_EAR_THRESHOLD : 0.26;
const POSTURE_THRESHOLD_Y = 0.7; 
const DISTANCE_THRESHOLD_RATIO = 0.4; 
const LIGHT_THRESHOLD = 40; 

// --- 1. INPUT TRACKING ---
document.addEventListener('keydown', () => {
    keyPressCount++;
    if(keysDisplay) keysDisplay.innerText = keyPressCount;
});

document.addEventListener('mousemove', (e) => {
    if (lastMouseX !== 0 && lastMouseY !== 0) {
        let dist = Math.sqrt(Math.pow(e.clientX - lastMouseX, 2) + Math.pow(e.clientY - lastMouseY, 2));
        mouseDistance += dist;
        if(mouseDisplay) mouseDisplay.innerText = Math.round(mouseDistance);
    }
    lastMouseX = e.clientX;
    lastMouseY = e.clientY;
});

// --- 2. ERGONOMICS & LIGHTING ---
function checkLighting(image) {
    if (Math.random() > 0.05) return; 

    const p = canvasCtx.getImageData(320, 240, 1, 1).data;
    const brightness = (p[0] + p[1] + p[2]) / 3;

    if (brightness < LIGHT_THRESHOLD) {
        lightAlert.classList.remove('d-none');
        ergoOverlay.classList.remove('d-none');
        // Trigger System Notification
        sendSystemNotification("Low Light Detected 💡", "Please turn on a light to reduce eye strain.");
    } else {
        lightAlert.classList.add('d-none');
    }
}

function checkPostureAndDistance(landmarks) {
    ergoOverlay.classList.remove('d-none');

    // 1. Posture (Slouching)
    const noseTip = landmarks[1];
    if (noseTip.y > POSTURE_THRESHOLD_Y) {
        postureAlert.classList.remove('d-none');
        // Trigger System Notification
        sendSystemNotification("Poor Posture Detected ⚠️", "You are slouching! Please sit up straight.");
    } else {
        postureAlert.classList.add('d-none');
    }

    // 2. Distance (Too Close)
    const leftCheek = landmarks[234];
    const rightCheek = landmarks[454];
    const faceWidth = Math.abs(leftCheek.x - rightCheek.x);

    if (faceWidth > DISTANCE_THRESHOLD_RATIO) {
        distanceAlert.classList.remove('d-none');
        // Trigger System Notification
        sendSystemNotification("Too Close to Screen 🛑", "Please lean back to protect your eyes.");
    } else {
        distanceAlert.classList.add('d-none');
    }
}

// --- 3. BLINK & FACE LOGIC ---
function getDistance(p1, p2) {
    return Math.sqrt(Math.pow(p1.x - p2.x, 2) + Math.pow(p1.y - p2.y, 2));
}

function calculateEAR(landmarks, indices) {
    const p1 = landmarks[indices[0]];
    const p2 = landmarks[indices[1]];
    const p3 = landmarks[indices[2]];
    const p4 = landmarks[indices[3]];
    const p5 = landmarks[indices[4]];
    const p6 = landmarks[indices[5]];
    const dist1 = getDistance(p2, p6);
    const dist2 = getDistance(p3, p5);
    const distH = getDistance(p1, p4);
    return (dist1 + dist2) / (2.0 * distH);
}

function onFaceMeshResults(results) {
    if (loadingMsg.style.display !== 'none') {
        loadingMsg.style.display = 'none';
    }
    
    canvasCtx.save();
    canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);
    canvasCtx.drawImage(results.image, 0, 0, canvasElement.width, canvasElement.height);

    checkLighting(results.image);

    if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
        const landmarks = results.multiFaceLandmarks[0];
        
        checkPostureAndDistance(landmarks);

        const LEFT_EYE = [362, 385, 387, 263, 373, 380];
        const RIGHT_EYE = [33, 160, 158, 133, 153, 144];
        const leftEAR = calculateEAR(landmarks, LEFT_EYE);
        const rightEAR = calculateEAR(landmarks, RIGHT_EYE);
        
        currentEAR = (leftEAR + rightEAR) / 2.0;
        totalEAR += currentEAR;
        earReadings++;

        earDisplay.innerText = currentEAR.toFixed(2);

        if (currentEAR < EAR_THRESHOLD) {
            if (!isBlinking) { isBlinking = true; }
        } else {
            if (isBlinking) {
                blinkCount++;
                blinkCountDisplay.innerText = blinkCount;
                isBlinking = false;
            }
        }
        
        drawConnectors(canvasCtx, landmarks, FACEMESH_TESSELATION, {color: '#C0C0C070', lineWidth: 1});
    }
    
    canvasCtx.font = "30px Arial";
    canvasCtx.fillStyle = "yellow";
    canvasCtx.fillText(currentEmotion, 50, 50);
    
    canvasCtx.restore();
}

// --- 4. EMOTION LOGIC ---
async function loadEmotionModel() {
    console.log("Loading Emotion Models...");
    const MODEL_URL = 'https://justadudewhohacks.github.io/face-api.js/models';
    await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL);
    await faceapi.nets.faceExpressionNet.loadFromUri(MODEL_URL);
    console.log("Emotion Models Loaded!");
}

async function detectEmotion() {
    if (!videoElement.paused && !videoElement.ended) {
        const detections = await faceapi.detectAllFaces(videoElement, new faceapi.TinyFaceDetectorOptions()).withFaceExpressions();
        if (detections.length > 0) {
            const expressions = detections[0].expressions;
            const maxEmotion = Object.keys(expressions).reduce((a, b) => expressions[a] > expressions[b] ? a : b);
            currentEmotion = maxEmotion.charAt(0).toUpperCase() + maxEmotion.slice(1); 
            statusBadge.innerText = currentEmotion;
            
            if(currentEmotion === 'Sad' || currentEmotion === 'Angry' || currentEmotion === 'Fearful') {
                statusBadge.className = "badge bg-danger";
            } else if (currentEmotion === 'Happy') {
                statusBadge.className = "badge bg-success";
            } else {
                statusBadge.className = "badge bg-secondary";
            }
        }
    }
    setTimeout(detectEmotion, 500);
}

// --- INIT ---
(async function main() {
    try {
        // Request Notification Permission on Load
        requestNotificationPermission();

        await loadEmotionModel();
        const faceMesh = new FaceMesh({locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`});
        faceMesh.setOptions({ maxNumFaces: 1, refineLandmarks: true, minDetectionConfidence: 0.5, minTrackingConfidence: 0.5 });
        faceMesh.onResults(onFaceMeshResults);

        const camera = new Camera(videoElement, {
            onFrame: async () => { await faceMesh.send({image: videoElement}); },
            width: 640, height: 480
        });
        await camera.start();
        detectEmotion(); 
    } catch (error) {
        console.error("Init Error:", error);
        alert("Error initializing AI.");
    }
})();

// --- 5. BACKEND SYNC ---
setInterval(() => {
    const sessionAvgEAR = earReadings > 0 ? (totalEAR / earReadings) : 0;
    fetch('/api/update_session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            blinks: blinkCount,
            emotion: currentEmotion,
            keys: keyPressCount,
            mouse: Math.round(mouseDistance),
            current_ear: currentEAR,
            session_avg_ear: sessionAvgEAR
        })
    }).catch(e => console.log("Sync error:", e));
}, 4000);

stopBtn.addEventListener('click', () => { window.location.href = "/generate_report"; });

// --- ZEN LOGIC ---
let zenInterval;
function startZenRoutine() {
    zenOverlay.style.display = 'flex';
    const updateBreath = () => {
        zenText.innerText = "Inhale... (Expand)";
        setTimeout(() => { if(zenOverlay.style.display === 'flex') zenText.innerText = "Hold..."; }, 4000);
        setTimeout(() => { if(zenOverlay.style.display === 'flex') zenText.innerText = "Exhale... (Relax)"; }, 6000);
    };
    updateBreath();
    zenInterval = setInterval(updateBreath, 10000);
}
function stopZenRoutine() {
    zenOverlay.style.display = 'none';
    clearInterval(zenInterval);
}
if(zenBtn) zenBtn.addEventListener('click', startZenRoutine);
if(closeZenBtn) closeZenBtn.addEventListener('click', stopZenRoutine);