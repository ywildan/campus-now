/* Campus Now - Web UI logic
   Fetches from local API and updates the UI in real-time.
   Uses Asia/Jakarta timezone via the server. */

const API_BASE = '/api';
const REFRESH_INTERVAL = 60000; // 60 seconds

// DOM elements
const dayNameEl = document.getElementById('dayName');
const dateTextEl = document.getElementById('dateText');
const stateLabelEl = document.getElementById('stateLabel');
const subjectEl = document.getElementById('subject');
const timeRangeEl = document.getElementById('timeRange');
const roomEl = document.getElementById('room');
const countdownEl = document.getElementById('countdown');
const countdownValueEl = document.getElementById('countdownValue');
const endsInEl = document.getElementById('endsIn');
const endsInValueEl = document.getElementById('endsInValue');
const progressContainerEl = document.getElementById('progressContainer');
const progressBarEl = document.getElementById('progressBar');
const progressHandleEl = document.getElementById('progressHandle');
const progressTextEl = document.getElementById('progressText');
const classListEl = document.getElementById('classList');

// State
let currentStatus = null;

async function fetchAPI(path) {
    try {
        const resp = await fetch(`${API_BASE}${path}`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (err) {
        console.error('API error:', err);
        return null;
    }
}

function formatTime(str) {
    return str;
}

function updateDateDisplay() {
    const now = new Date();
    const options = {
        weekday: 'long',
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        timeZone: 'Asia/Jakarta'
    };
    const formatted = now.toLocaleDateString('en-US', options);
    const parts = formatted.split(', ');
    if (parts.length >= 2) {
        dayNameEl.textContent = parts[0].toUpperCase();
        dateTextEl.textContent = parts.slice(1).join(', ');
    }
}

function renderMainCard(status) {
    if (!status) {
        stateLabelEl.textContent = 'ERROR';
        subjectEl.textContent = 'Unable to load schedule';
        timeRangeEl.textContent = '';
        roomEl.textContent = '';
        return;
    }

    const isNow = status.state === 'now';
    const current = status.current;
    const next = status.next;

    // Hide all conditional elements
    countdownEl.style.display = 'none';
    endsInEl.style.display = 'none';
    progressContainerEl.style.display = 'none';
    progressTextEl.style.display = 'none';

    if (isNow && current) {
        // Current class
        stateLabelEl.textContent = 'NOW';
        subjectEl.textContent = current.subject;
        timeRangeEl.textContent = `${current.start} — ${current.end}`;
        roomEl.textContent = current.room;

        // Show "Ends in" and progress
        if (current.minutes_remaining !== null) {
            endsInEl.style.display = 'block';
            endsInValueEl.textContent = `${current.minutes_remaining} min`;
        }

        if (current.progress !== null && current.progress >= 0) {
            progressContainerEl.style.display = 'block';
            const pct = Math.max(0, Math.min(100, current.progress * 100));
            progressBarEl.style.width = `${pct}%`;
            progressHandleEl.style.left = `${pct}%`;

            progressTextEl.style.display = 'block';
            progressTextEl.textContent = `${Math.round(pct)}% complete`;
        }
    } else {
        // Next class
        stateLabelEl.textContent = 'NEXT CLASS';

        if (next) {
            subjectEl.textContent = next.subject;
            timeRangeEl.textContent = `${next.start} — ${next.end}`;
            roomEl.textContent = next.room;

            countdownEl.style.display = 'block';
            if (next.minutes_until !== null) {
                countdownValueEl.textContent = formatDurationText(next.minutes_until);
            }
        } else {
            // No classes found
            subjectEl.textContent = 'No upcoming classes';
            timeRangeEl.textContent = '';
            roomEl.textContent = '';

            if (status.classes_finished) {
                stateLabelEl.textContent = 'CLASSES FINISHED';
                subjectEl.textContent = 'Enjoy your day!';
            }
        }
    }
}

function formatDurationText(minutes) {
    if (minutes < 60) return `${minutes} min`;
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    if (m === 0) return `${h}h`;
    return `${h}h ${m}m`;
}

function renderToday(todaysClasses, current) {
    classListEl.innerHTML = '';

    if (!todaysClasses || todaysClasses.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'class-item';
        empty.innerHTML = '<span style="color: var(--text-secondary)">No classes today</span>';
        classListEl.appendChild(empty);
        return;
    }

    todaysClasses.forEach(cls => {
        const item = document.createElement('div');
        item.className = 'class-item';
        if (current && cls.subject === current.subject) {
            item.classList.add('current');
        }

        const left = document.createElement('div');
        left.style.display = 'flex';
        left.style.flexDirection = 'column';
        left.innerHTML = `
            <span class="class-subject">${cls.subject}</span>
            <span class="class-time">${cls.start} — ${cls.end}</span>
        `;

        const right = document.createElement('div');
        right.className = 'class-room';
        right.textContent = cls.room;

        item.appendChild(left);
        item.appendChild(right);
        classListEl.appendChild(item);
    });
}

function updateCountdownLive() {
    // Live countdown ticker for the "Starts in" or "Ends in" text
    if (currentStatus && currentStatus.current) {
        // For current class: show progress tick
        const current = currentStatus.current;
        if (current.minutes_remaining !== null) {
            endsInValueEl.textContent = `${current.minutes_remaining} min`;
        }
        if (current.progress !== null) {
            const pct = Math.max(0, Math.min(100, current.progress * 100));
            progressBarEl.style.width = `${pct}%`;
            progressHandleEl.style.left = `${pct}%`;
            progressTextEl.textContent = `${Math.round(pct)}% complete`;
        }
    }
    // For next class countdown, the value updates every minute via API refresh
}

async function refresh() {
    const status = await fetchAPI('/status');
    if (status) {
        currentStatus = status;
        updateDateDisplay();
        renderMainCard(status);

        // Today's classes come from the status response
        if (status.today) {
            renderToday(status.today, status.current);
        }
    }
}

// Initialize and set up polling
document.addEventListener('DOMContentLoaded', () => {
    refresh();
    setInterval(refresh, REFRESH_INTERVAL);
});
