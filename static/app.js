let cats = [];
let currentWeekOffset = 0;
let ganttDateOffset = 0;
const hub = document.getElementById('hub');
const svg = document.getElementById('hit-surface');

const chartColors = [
    "#00e5ff", "#ff4b2b", "#ffd166", "#06d6a0", "#9b5de5",
    "#f15bb5", "#fee440", "#00bbf9", "#f77f00", "#80ed99"
];

function format(s, full=false) {
    let h = Math.floor(s / 3600).toString().padStart(2, '0');
    let m = Math.floor((s % 3600) / 60).toString().padStart(2, '0');
    let sec = (s % 60).toString().padStart(2, '0');
    return full ? `${h}:${m}:${sec}` : `${m}:${sec}`;
}

function secondsToLabel(s) {
    let h = Math.floor(s / 3600);
    let m = Math.floor((s % 3600) / 60);
    return `${h}h ${m}m`;
}

function visibleCategories(categories) {
    return categories.filter(c => c !== "Nothing");
}

function visibleDayTotal(day) {
    return Object.entries(day.totals)
        .filter(([cat]) => cat !== "Nothing")
        .reduce((sum, [, seconds]) => sum + seconds, 0);
}

function addDays(date, days) {
    const d = new Date(date);
    d.setDate(d.getDate() + days);
    return d;
}

function localDateString(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
}

function logicalDateString(date) {
    const shifted = new Date(date);
    shifted.setHours(shifted.getHours() - 6, shifted.getMinutes(), shifted.getSeconds(), shifted.getMilliseconds());
    return localDateString(shifted);
}

function timeToTimelineMinutes(dateTimeText) {
    const timePart = dateTimeText.split(' ')[1] || '00:00:00';
    const parts = timePart.split(':').map(Number);
    const totalMinutes = parts[0] * 60 + parts[1] + (parts[2] || 0) / 60;
    return (totalMinutes - 360 + 1440) % 1440;
}

function displayTime(dateTimeText) {
    const timePart = dateTimeText.split(' ')[1] || '00:00:00';
    return timePart.slice(0, 5);
}

function changeWeek(direction) {
    if (direction === 0) {
        currentWeekOffset = 0;
    } else {
        currentWeekOffset += direction;
    }
    loadWeekChart();
}

function loadWeekChart() {
    window.pywebview.api.get_week_report(currentWeekOffset).then(data => {
        document.getElementById("week-label").innerText =
            `${data.week_start} → ${data.week_end}`;

        const chart = document.getElementById("week-chart");
        const legend = document.getElementById("week-legend");
        chart.innerHTML = "";
        legend.innerHTML = "";

        const chartCategories = visibleCategories(data.categories);

        chartCategories.forEach((cat, i) => {
            const item = document.createElement("div");
            item.className = "legend-item";

            const dot = document.createElement("div");
            dot.className = "legend-dot";
            dot.style.background = chartColors[i % chartColors.length];

            const text = document.createElement("span");
            text.innerText = cat;

            item.appendChild(dot);
            item.appendChild(text);
            legend.appendChild(item);
        });

        const maxDayTotal = Math.max(
            1,
            ...data.days.map(day => visibleDayTotal(day))
        );

        data.days.forEach(day => {
            const dayTotal = visibleDayTotal(day);

            const wrapper = document.createElement("div");
            wrapper.className = "bar-wrapper";

            const bar = document.createElement("div");
            bar.className = "bar";
            bar.style.height = `${Math.max(4, (dayTotal / maxDayTotal) * 150)}px`;
            bar.title = `${day.date} — ${secondsToLabel(dayTotal)}`;

            chartCategories.forEach((cat, i) => {
                const seconds = day.totals[cat] || 0;
                if (seconds <= 0 || dayTotal <= 0) return;

                const segment = document.createElement("div");
                segment.style.height = `${(seconds / dayTotal) * 100}%`;
                segment.style.background = chartColors[i % chartColors.length];
                segment.style.position = "relative";
                segment.title = `${cat}: ${secondsToLabel(seconds)}`;

                if (cat === "CivilAgent") {
                    const catLabel = document.createElement("div");
                    catLabel.style.cssText = "position:absolute; top:1px; left:0; right:0; text-align:center; font-size:8px; color:#000; font-family:monospace; font-weight:bold; pointer-events:none; overflow:hidden;";
                    catLabel.innerText = secondsToLabel(seconds);
                    segment.appendChild(catLabel);
                }

                bar.appendChild(segment);
            });

            const label = document.createElement("div");
            label.className = "bar-label";
            label.innerText = day.label;

            wrapper.appendChild(bar);
            wrapper.appendChild(label);
            chart.appendChild(wrapper);
        });
    });
}

function toggleSettings() {
    const panel = document.getElementById('settings-panel');
    const gantt = document.getElementById('gantt-panel');
    const ui = document.getElementById('app-ui');
    const isVisible = panel.style.display === 'block';
    if (!isVisible) {
        gantt.style.display = 'none';
        window.pywebview.api.get_init_data().then(data => {
            const table = document.getElementById('history-table');
            table.innerHTML = data.history.map(h => `<tr><td>${h.name}</td><td>${h.time}</td></tr>`).join('');
            document.getElementById('cat-input').value = data.categories.filter(c => c !== "Nothing").join('\n');
            loadWeekChart();
        });
    }
    panel.style.display = isVisible ? 'none' : 'block';
    ui.className = isVisible ? 'main-container' : 'main-container blur';
}

function toggleGantt() {
    const panel = document.getElementById('gantt-panel');
    const settings = document.getElementById('settings-panel');
    const ui = document.getElementById('app-ui');
    const isVisible = panel.style.display === 'block';

    if (!isVisible) {
        settings.style.display = 'none';
        ganttDateOffset = 0;
        loadGanttChart();
    }

    panel.style.display = isVisible ? 'none' : 'block';
    ui.className = isVisible ? 'main-container' : 'main-container blur';
}

function shiftGanttDay(direction) {
    if (direction === 0) {
        ganttDateOffset = 0;
    } else {
        ganttDateOffset += direction;
    }
    loadGanttChart();
}

let ganttData = null;      // last report fetched from get_gantt_report
let editingSessionId = null;
let dragState = null;      // in-progress drag/resize/create, see startBlockDrag/startLaneCreate

function loadGanttChart() {
    if (dragState) return; // don't clobber the chart mid-drag
    const targetDate = logicalDateString(addDays(new Date(), ganttDateOffset));
    window.pywebview.api.get_gantt_report(targetDate).then(data => {
        ganttData = data;
        document.getElementById('gantt-date').innerText = data.date;
        renderGantt(data);
    });
}

function minutesToTimeString(dateStr, minutes) {
    // minutes is on the gantt's 0..1440 axis, where 0 = 06:00 of dateStr.
    const base = new Date(`${dateStr}T06:00:00`);
    base.setMinutes(base.getMinutes() + minutes);
    const y = base.getFullYear();
    const m = String(base.getMonth() + 1).padStart(2, '0');
    const d = String(base.getDate()).padStart(2, '0');
    const hh = String(base.getHours()).padStart(2, '0');
    const mm = String(base.getMinutes()).padStart(2, '0');
    const ss = String(base.getSeconds()).padStart(2, '0');
    return `${y}-${m}-${d} ${hh}:${mm}:${ss}`;
}

function renderGantt(data) {
    const chart = document.getElementById('gantt-chart');
    chart.innerHTML = '';

    const sessions = data.sessions || [];

    const axis = document.createElement('div');
    axis.className = 'gantt-axis';
    [6, 12, 18, 24, 30].forEach(hour => {
        const mark = document.createElement('div');
        mark.className = 'axis-mark';
        mark.style.left = `${((hour - 6) / 24) * 100}%`;
        mark.innerText = `${String(hour % 24).padStart(2, '0')}:00`;
        axis.appendChild(mark);
    });
    chart.appendChild(axis);

    const rowCategories = data.categories.filter(cat => cat !== 'Nothing' && sessions.some(s => s.category === cat));

    if (rowCategories.length === 0) {
        chart.innerHTML += '<div class="gantt-empty">No sessions recorded for this day yet. Drag on a category\'s row (once it has one) to add more, or use STATS/EDIT to add tasks.</div>';
        return;
    }

    rowCategories.forEach(cat => {
        const row = document.createElement('div');
        row.className = 'gantt-row';

        const label = document.createElement('div');
        label.className = 'gantt-label';
        label.innerText = cat;
        label.title = cat;

        const lane = document.createElement('div');
        lane.className = 'gantt-lane';
        lane.dataset.category = cat;
        lane.addEventListener('mousedown', onLaneMouseDown);

        sessions.filter(s => s.category === cat).forEach(s => {
            lane.appendChild(buildGanttBlock(s, data));
        });

        row.appendChild(label);
        row.appendChild(lane);
        chart.appendChild(row);
    });
}

function buildGanttBlock(s, data) {
    const startMin = Math.max(0, Math.min(1440, timeToTimelineMinutes(s.start)));
    let endMin = Math.max(0, Math.min(1440, timeToTimelineMinutes(s.end)));
    if (endMin <= startMin) {
        endMin = 1440;
    }
    const left = (startMin / 1440) * 100;
    const width = Math.max(0.25, ((endMin - startMin) / 1440) * 100);
    const colorIndex = Math.max(0, data.categories.indexOf(s.category) - 1);

    const block = document.createElement('div');
    block.className = 'gantt-block' + (s.live ? ' live' : '') + (s.clipped ? ' clipped' : '');
    block.style.left = `${left}%`;
    block.style.width = `${width}%`;
    block.style.background = chartColors[colorIndex % chartColors.length];
    block.title = `${s.category}\n${displayTime(s.start)} → ${displayTime(s.end)}\n${secondsToLabel(s.duration || 0)}${s.live ? ' / live' : ''}${s.clipped ? '\n(continues past this day)' : ''}`;
    block.dataset.sessionId = s.session_id || '';

    if (s.live || !s.session_id) {
        return block; // the in-progress session isn't editable here
    }

    const leftHandle = document.createElement('div');
    leftHandle.className = 'gantt-handle left';
    const rightHandle = document.createElement('div');
    rightHandle.className = 'gantt-handle right';
    block.appendChild(leftHandle);
    block.appendChild(rightHandle);

    leftHandle.addEventListener('mousedown', e => { e._ganttHandled = true; startBlockDrag(e, s, 'resize-left'); });
    rightHandle.addEventListener('mousedown', e => { e._ganttHandled = true; startBlockDrag(e, s, 'resize-right'); });
    block.addEventListener('mousedown', e => {
        if (e._ganttHandled) return;
        e._ganttHandled = true;
        startBlockDrag(e, s, 'move');
    });
    block.addEventListener('dblclick', e => {
        e.stopPropagation();
        openSessionEditor(s);
    });

    return block;
}

function laneMinutesFromEvent(lane, clientX) {
    const rect = lane.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    return Math.round(ratio * 1440);
}

function startBlockDrag(e, session, mode) {
    e.preventDefault();
    e.stopPropagation();
    const blockEl = document.querySelector(`.gantt-block[data-session-id="${session.session_id}"]`);
    const lane = blockEl.parentElement;

    dragState = {
        mode,
        session,
        lane,
        blockEl,
        startClientX: e.clientX,
        origStartMin: timeToTimelineMinutes(session.start),
        origEndMin: timeToTimelineMinutes(session.end),
        targetCategory: session.category, // only changes for mode === 'move'
    };
    blockEl.classList.add('dragging');

    window.addEventListener('mousemove', onBlockDragMove);
    window.addEventListener('mouseup', onBlockDragEnd);
}

const MIN_SESSION_MINUTES = 5; // keeps rounding to whole minutes from ever producing end <= start

function laneUnderPoint(clientX, clientY) {
    const el = document.elementFromPoint(clientX, clientY);
    return el ? el.closest('.gantt-lane') : null;
}

function onBlockDragMove(e) {
    if (!dragState) return;
    const { mode, blockEl, startClientX, origStartMin, origEndMin } = dragState;
    const rect = dragState.lane.getBoundingClientRect();
    const deltaMin = Math.round(((e.clientX - startClientX) / rect.width) * 1440);

    let newStart = origStartMin;
    let newEnd = origEndMin;

    if (mode === 'move') {
        const span = origEndMin - origStartMin;
        newStart = Math.max(0, Math.min(1440 - span, origStartMin + deltaMin));
        newEnd = newStart + span;

        // Vertical drag between rows re-targets the block at a different
        // category/lane; horizontal position stays computed against the
        // lane currently under the cursor.
        const hoverLane = laneUnderPoint(e.clientX, e.clientY);
        if (hoverLane && hoverLane !== blockEl.parentElement) {
            hoverLane.appendChild(blockEl);
            dragState.targetCategory = hoverLane.dataset.category;
        }
    } else if (mode === 'resize-left') {
        newStart = Math.max(0, Math.min(origEndMin - MIN_SESSION_MINUTES, origStartMin + deltaMin));
    } else if (mode === 'resize-right') {
        newEnd = Math.min(1440, Math.max(origStartMin + MIN_SESSION_MINUTES, origEndMin + deltaMin));
    }

    dragState.newStartMin = newStart;
    dragState.newEndMin = newEnd;

    blockEl.style.left = `${(newStart / 1440) * 100}%`;
    blockEl.style.width = `${Math.max(0.25, ((newEnd - newStart) / 1440) * 100)}%`;
    blockEl.title = `${dragState.targetCategory}\n${displayTime(minutesToTimeString(ganttData.date, newStart))} → ${displayTime(minutesToTimeString(ganttData.date, newEnd))}`;
}

function onBlockDragEnd() {
    if (!dragState) return;
    const { session, blockEl, newStartMin, newEndMin, targetCategory } = dragState;
    window.removeEventListener('mousemove', onBlockDragMove);
    window.removeEventListener('mouseup', onBlockDragEnd);
    blockEl.classList.remove('dragging');

    const timeMoved = newStartMin !== undefined && (newStartMin !== dragState.origStartMin || newEndMin !== dragState.origEndMin);
    const categoryChanged = targetCategory !== session.category;
    dragState = null;

    if (!timeMoved && !categoryChanged) return;

    const newStart = minutesToTimeString(ganttData.date, newStartMin);
    const newEnd = minutesToTimeString(ganttData.date, newEndMin);
    const categoryArg = categoryChanged ? targetCategory : null;
    window.pywebview.api.update_gantt_session(session.session_id, newStart, newEnd, categoryArg).then(result => {
        if (!result) {
            alert('Could not update the session (end must be after start).');
        }
        loadGanttChart();
    });
}

function onLaneMouseDown(e) {
    if (e._ganttHandled) return; // a block/handle already started its own drag
    if (e.target !== e.currentTarget) return; // ignore clicks that started on a block
    e.preventDefault();
    const lane = e.currentTarget;
    const startMin = laneMinutesFromEvent(lane, e.clientX);

    const draft = document.createElement('div');
    draft.className = 'gantt-draft';
    draft.style.left = `${(startMin / 1440) * 100}%`;
    draft.style.width = '0%';
    lane.appendChild(draft);

    dragState = { mode: 'create', lane, draft, startMin, currentMin: startMin };

    window.addEventListener('mousemove', onLaneCreateMove);
    window.addEventListener('mouseup', onLaneCreateEnd);
}

function onLaneCreateMove(e) {
    if (!dragState || dragState.mode !== 'create') return;
    const { lane, draft, startMin } = dragState;
    const currentMin = laneMinutesFromEvent(lane, e.clientX);
    dragState.currentMin = currentMin;

    const lo = Math.min(startMin, currentMin);
    const hi = Math.max(startMin, currentMin);
    draft.style.left = `${(lo / 1440) * 100}%`;
    draft.style.width = `${Math.max(0.25, ((hi - lo) / 1440) * 100)}%`;
}

function onLaneCreateEnd() {
    if (!dragState || dragState.mode !== 'create') return;
    const { lane, draft, startMin, currentMin } = dragState;
    window.removeEventListener('mousemove', onLaneCreateMove);
    window.removeEventListener('mouseup', onLaneCreateEnd);
    draft.remove();
    dragState = null;

    const lo = Math.min(startMin, currentMin);
    const hi = Math.max(startMin, currentMin);
    if (hi - lo < 2) return; // treat as a stray click, not a create-drag

    const category = lane.dataset.category;
    const start = minutesToTimeString(ganttData.date, lo);
    const end = minutesToTimeString(ganttData.date, hi);

    window.pywebview.api.create_gantt_session(category, start, end).then(result => {
        if (!result) {
            alert('Could not create the session.');
        }
        loadGanttChart();
    });
}

function openSessionEditor(session) {
    editingSessionId = session.session_id;

    const select = document.getElementById('edit-category');
    select.innerHTML = (ganttData.categories || []).filter(c => c !== 'Nothing')
        .map(c => `<option value="${c}"${c === session.category ? ' selected' : ''}>${c}</option>`).join('');

    document.getElementById('edit-start').value = session.start;
    document.getElementById('edit-end').value = session.end;
    document.getElementById('edit-error').innerText = session.clipped
        ? 'This block continues past this day; editing changes the full session.'
        : '';

    document.getElementById('session-edit-panel').style.display = 'block';
}

function closeSessionEditor() {
    document.getElementById('session-edit-panel').style.display = 'none';
    editingSessionId = null;
}

function submitSessionEdit() {
    const category = document.getElementById('edit-category').value;
    const start = document.getElementById('edit-start').value.trim();
    const end = document.getElementById('edit-end').value.trim();
    const errorEl = document.getElementById('edit-error');

    window.pywebview.api.update_gantt_session(editingSessionId, start, end, category).then(result => {
        if (!result) {
            errorEl.innerText = 'Invalid times — make sure the format is YYYY-MM-DD HH:MM:SS and end is after start.';
            return;
        }
        closeSessionEditor();
        loadGanttChart();
    });
}

function deleteSessionFromEditor() {
    if (!editingSessionId) return;

    window.pywebview.api.delete_gantt_session(editingSessionId).then(() => {
        closeSessionEditor();
        loadGanttChart();
    });
}

function undoGanttEdit() {
    window.pywebview.api.undo_last_gantt_edit().then(action => {
        if (!action) return; // nothing to undo
        loadGanttChart();
    });
}

document.addEventListener('keydown', e => {
    const gantt = document.getElementById('gantt-panel');
    if (gantt.style.display !== 'block') return;
    // e.code is the physical key position (KeyZ), so this works regardless
    // of keyboard layout (e.g. Persian), unlike e.key which reflects the
    // typed character.
    if ((e.ctrlKey || e.metaKey) && e.code === 'KeyZ') {
        e.preventDefault();
        undoGanttEdit();
    }
});

function resetCurrent() {
    if(confirm("Reset current session?")) window.pywebview.api.reset_timer();
}

function saveSettings() {
    const lines = document.getElementById('cat-input').value.split('\n').filter(l => l.trim() !== "");
    window.pywebview.api.update_config(lines).then(initUI);
    toggleSettings();
}

function initUI(data) {
    cats = data.categories;
    svg.innerHTML = '';
    document.querySelectorAll('.label').forEach(e => e.remove());
    const step = 360 / cats.length;
    cats.forEach((name, i) => {
        const centerAngle = i * step;
        const sRad = (centerAngle - step/2 - 90) * Math.PI / 180, eRad = (centerAngle + step/2 - 90) * Math.PI / 180;
        const x1 = 50 + 50 * Math.cos(sRad), y1 = 50 + 50 * Math.sin(sRad), x2 = 50 + 50 * Math.cos(eRad), y2 = 50 + 50 * Math.sin(eRad);
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", `M 50 50 L ${x1} ${y1} A 50 50 0 0 1 ${x2} ${y2} Z`);
        path.setAttribute("class", "slice");
        path.onclick = () => select(name, centerAngle);
        svg.appendChild(path);
        const label = document.createElement('div');
        label.className = 'label';
        label.id = 'lbl-' + name;
        label.innerText = name;
        const rad = (centerAngle - 90) * (Math.PI / 180);
        label.style.left = (260 + 210 * Math.cos(rad) - 55) + 'px';
        label.style.top = (260 + 210 * Math.sin(rad) - 10) + 'px';
        document.getElementById('app-ui').appendChild(label);
    });
    const activeIdx = cats.indexOf(data.active);
    select(data.active, activeIdx * step);
}

window.addEventListener('pywebviewready', () => window.pywebview.api.get_init_data().then(initUI));

function select(name, deg) {
    hub.style.transform = `rotate(${deg}deg)`;
    window.pywebview.api.set_category(name);
    document.querySelectorAll('.label').forEach(l => l.classList.remove('active'));
    if(document.getElementById('lbl-' + name)) document.getElementById('lbl-' + name).classList.add('active');
}

setInterval(() => {
    if(window.pywebview.api) {
        window.pywebview.api.get_status().then(s => {
            document.getElementById('session-time').innerText = format(s.session);
            document.getElementById('total-time').innerText = format(s.total, true);
        });
    }
}, 1000);

// The Gantt chart only needs a periodic refresh (it re-parses history
// on the Python side), not a full-second tick like the live timer.
setInterval(() => {
    if (window.pywebview.api && document.getElementById('gantt-panel').style.display === 'block') {
        loadGanttChart();
    }
}, 5000);
