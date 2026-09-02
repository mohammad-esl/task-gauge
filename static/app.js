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
            `${gregorianStrToJalaliStr(data.week_start)} → ${gregorianStrToJalaliStr(data.week_end)}`;

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
            bar.title = `${gregorianStrToJalaliStr(day.date)} — ${secondsToLabel(dayTotal)}`;

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
    const stats = document.getElementById('stats-panel');
    const ui = document.getElementById('app-ui');
    const isVisible = panel.style.display === 'block';
    if (!isVisible) {
        gantt.style.display = 'none';
        stats.style.display = 'none';
        window.pywebview.api.get_init_data().then(data => {
            const table = document.getElementById('history-table');
            table.innerHTML = data.history.map(h => `<tr><td>${h.name}</td><td>${h.time}</td></tr>`).join('');
            taskRows = data.categories.filter(c => c !== "Nothing");
            window.pywebview.api.categories_with_history().then(names => {
                categoriesWithHistory = new Set(names);
                renderTaskRows();
            });
            loadWeekChart();

            const subtaskSelect = document.getElementById('subtask-window-category');
            subtaskSelect.innerHTML = data.categories.filter(c => c !== 'Nothing')
                .map(c => `<option value="${c}">${c}</option>`).join('');
        });
    }
    panel.style.display = isVisible ? 'none' : 'block';
    ui.className = isVisible ? 'main-container' : 'main-container blur';
}

function toggleStats() {
    const panel = document.getElementById('stats-panel');
    const settings = document.getElementById('settings-panel');
    const gantt = document.getElementById('gantt-panel');
    const ui = document.getElementById('app-ui');
    const isVisible = panel.style.display === 'block';
    if (!isVisible) {
        settings.style.display = 'none';
        gantt.style.display = 'none';
        window.pywebview.api.get_init_data().then(data => {
            const rangeSelect = document.getElementById('range-category');
            rangeSelect.innerHTML = data.categories.map(c => `<option value="${c}">${c}</option>`).join('');
            const todayJalali = gregorianStrToJalaliStr(localDateString(new Date()));
            document.getElementById('range-start').value = todayJalali;
            document.getElementById('range-end').value = todayJalali;
            document.getElementById('range-result').innerText = '';
        });
    }
    panel.style.display = isVisible ? 'none' : 'block';
    ui.className = isVisible ? 'main-container' : 'main-container blur';
}

function loadRangeStats() {
    const category = document.getElementById('range-category').value;
    const startJalali = document.getElementById('range-start').value;
    const endJalali = document.getElementById('range-end').value;
    const result = document.getElementById('range-result');
    if (!startJalali || !endJalali) {
        result.innerText = 'اول و آخر بازه رو انتخاب کن.';
        return;
    }
    const start = jalaliStrToGregorianStr(startJalali);
    const end = jalaliStrToGregorianStr(endJalali);
    if (start > end) {
        result.innerText = 'تاریخ شروع نباید بعد از تاریخ پایان باشه.';
        return;
    }
    window.pywebview.api.get_range_report(start, end).then(report => {
        const seconds = report.totals[category] || 0;
        const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60;
        result.innerText = `${category}: ${h}h ${m}m ${s}s (${startJalali} تا ${endJalali})`;
    });
}

let jalaliPickerTarget = null;   // id of the text input currently being edited
let jalaliPickerYear = null;
let jalaliPickerMonth = null;

function openJalaliPicker(inputId) {
    const input = document.getElementById(inputId);
    const picker = document.getElementById('jalali-picker');
    jalaliPickerTarget = inputId;

    const current = input.value ? input.value.split('/').map(Number) : null;
    const todayJalali = toJalali(...localDateString(new Date()).split('-').map(Number));
    jalaliPickerYear = current ? current[0] : todayJalali[0];
    jalaliPickerMonth = current ? current[1] : todayJalali[1];

    const rect = input.getBoundingClientRect();
    picker.style.left = rect.left + 'px';
    picker.style.top = (rect.bottom + 4) + 'px';
    picker.style.display = 'block';
    renderJalaliPicker();

    document.addEventListener('click', closeJalaliPickerOnOutsideClick, { capture: true });
}

function closeJalaliPickerOnOutsideClick(e) {
    const picker = document.getElementById('jalali-picker');
    const input = document.getElementById(jalaliPickerTarget);
    if (picker.contains(e.target) || e.target === input) return;
    picker.style.display = 'none';
    document.removeEventListener('click', closeJalaliPickerOnOutsideClick, { capture: true });
}

function jalaliPickerShiftMonth(direction) {
    jalaliPickerMonth += direction;
    if (jalaliPickerMonth < 1) { jalaliPickerMonth = 12; jalaliPickerYear -= 1; }
    if (jalaliPickerMonth > 12) { jalaliPickerMonth = 1; jalaliPickerYear += 1; }
    renderJalaliPicker();
}

function renderJalaliPicker() {
    document.getElementById('jalali-picker-title').innerText =
        `${JALALI_MONTHS[jalaliPickerMonth - 1]} ${jalaliPickerYear}`;

    const weekdays = document.getElementById('jalali-picker-weekdays');
    weekdays.innerHTML = JALALI_WEEKDAYS_SHORT.map(w => `<div>${w}</div>`).join('');

    const [gy, gm, gd] = toGregorian(jalaliPickerYear, jalaliPickerMonth, 1);
    const jsDate = new Date(gy, gm - 1, gd);
    const jsWeekday = jsDate.getDay(); // 0=Sun..6=Sat
    const firstCellOffset = (jsWeekday + 1) % 7; // convert to Sat=0..Fri=6

    const monthLength = jalaliMonthLength(jalaliPickerYear, jalaliPickerMonth);
    const selected = document.getElementById(jalaliPickerTarget).value;

    const grid = document.getElementById('jalali-picker-grid');
    grid.innerHTML = '';
    for (let i = 0; i < firstCellOffset; i += 1) {
        grid.innerHTML += '<div class="jalali-picker-day empty"></div>';
    }
    for (let day = 1; day <= monthLength; day += 1) {
        const dayStr = `${jalaliPickerYear}/${pad2(jalaliPickerMonth)}/${pad2(day)}`;
        const isSelected = dayStr === selected;
        grid.innerHTML += `<div class="jalali-picker-day${isSelected ? ' selected' : ''}" onclick="selectJalaliDay(${day})">${day}</div>`;
    }
}

function selectJalaliDay(day) {
    const dayStr = `${jalaliPickerYear}/${pad2(jalaliPickerMonth)}/${pad2(day)}`;
    document.getElementById(jalaliPickerTarget).value = dayStr;
    document.getElementById('jalali-picker').style.display = 'none';
    document.removeEventListener('click', closeJalaliPickerOnOutsideClick, { capture: true });
}

function toggleGantt() {
    const panel = document.getElementById('gantt-panel');
    const settings = document.getElementById('settings-panel');
    const stats = document.getElementById('stats-panel');
    const ui = document.getElementById('app-ui');
    const isVisible = panel.style.display === 'block';

    if (!isVisible) {
        settings.style.display = 'none';
        stats.style.display = 'none';
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
        document.getElementById('gantt-date').innerText = gregorianStrToJalaliStr(data.date);
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
const SNAP_MINUTES = 5;        // drag/resize snaps to this grid

function laneUnderPoint(clientX, clientY) {
    const el = document.elementFromPoint(clientX, clientY);
    return el ? el.closest('.gantt-lane') : null;
}

function snapMinutes(min) {
    return Math.round(min / SNAP_MINUTES) * SNAP_MINUTES;
}

// Other sessions in the same category today, excluding the one being
// dragged, as [startMin, endMin] pairs on the gantt's 0..1440 axis.
function neighborRangesForCategory(category, excludeSessionId) {
    return (ganttData.sessions || [])
        .filter(s => s.category === category && s.session_id !== excludeSessionId && !s.live)
        .map(s => [timeToTimelineMinutes(s.start), timeToTimelineMinutes(s.end)])
        .filter(([s, e]) => e > s);
}

// Clamps [start, end] so it doesn't overlap any neighbor range. Resizing
// simply can't push the moving edge past the nearest neighbor edge in its
// direction of travel. Moving preserves the original span and slides the
// whole block to sit flush against whichever neighbor it collided with,
// picking the neighbor that requires the smallest correction.
function clampAgainstNeighbors(start, end, neighbors, mode, origStart, origEnd) {
    if (mode === 'resize-left') {
        // The right edge (end) is fixed; can't drag start past the end of
        // any neighbor that lies to the left of (or overlaps) our fixed end.
        for (const [, nEnd] of neighbors) {
            if (nEnd <= end && nEnd > start) start = Math.max(start, nEnd);
        }
        return [start, end];
    }
    if (mode === 'resize-right') {
        // The left edge (start) is fixed; can't drag end past the start of
        // any neighbor that lies to the right of (or overlaps) our fixed start.
        for (const [nStart] of neighbors) {
            if (nStart >= start && nStart < end) end = Math.min(end, nStart);
        }
        return [start, end];
    }

    // move: find every neighbor we currently overlap, compute the minimal
    // slide (left or right) needed to clear each one, and apply whichever
    // single slide clears all of them (checked by re-validating after).
    const span = end - start;
    let candidateStart = start;
    let bestCorrection = null;

    for (const [nStart, nEnd] of neighbors) {
        const overlaps = start < nEnd && end > nStart;
        if (!overlaps) continue;
        const pushRightStart = nEnd;               // slide so our start sits at neighbor's end
        const pushLeftStart = nStart - span;        // slide so our end sits at neighbor's start
        const distRight = Math.abs(pushRightStart - start);
        const distLeft = Math.abs(pushLeftStart - start);
        const chosen = distRight <= distLeft ? pushRightStart : pushLeftStart;
        if (bestCorrection === null || Math.abs(chosen - start) < Math.abs(bestCorrection - start)) {
            bestCorrection = chosen;
        }
    }

    if (bestCorrection !== null) {
        candidateStart = Math.max(0, Math.min(1440 - span, bestCorrection));
    }

    // Re-check: the chosen slide might still collide with another neighbor
    // (tightly packed rows) — if so, fall back to not moving at all.
    let candidateEnd = candidateStart + span;
    const stillOverlaps = neighbors.some(([nStart, nEnd]) => candidateStart < nEnd && candidateEnd > nStart);
    if (stillOverlaps) {
        candidateStart = origStart;
        candidateEnd = origEnd;
    }

    return [candidateStart, candidateEnd];
}

function onBlockDragMove(e) {
    if (!dragState) return;
    const { mode, blockEl, startClientX, origStartMin, origEndMin, session } = dragState;
    const rect = dragState.lane.getBoundingClientRect();
    const deltaMin = Math.round(((e.clientX - startClientX) / rect.width) * 1440);

    let newStart = origStartMin;
    let newEnd = origEndMin;
    let targetCategory = dragState.targetCategory;

    if (mode === 'move') {
        const span = origEndMin - origStartMin;
        newStart = snapMinutes(Math.max(0, Math.min(1440 - span, origStartMin + deltaMin)));
        newEnd = newStart + span;

        // Vertical drag between rows re-targets the block at a different
        // category/lane; horizontal position stays computed against the
        // lane currently under the cursor.
        const hoverLane = laneUnderPoint(e.clientX, e.clientY);
        if (hoverLane && hoverLane !== blockEl.parentElement) {
            hoverLane.appendChild(blockEl);
            targetCategory = hoverLane.dataset.category;
            dragState.targetCategory = targetCategory;
        }
    } else if (mode === 'resize-left') {
        newStart = snapMinutes(Math.max(0, Math.min(origEndMin - MIN_SESSION_MINUTES, origStartMin + deltaMin)));
    } else if (mode === 'resize-right') {
        newEnd = snapMinutes(Math.min(1440, Math.max(origStartMin + MIN_SESSION_MINUTES, origEndMin + deltaMin)));
    }

    const neighbors = neighborRangesForCategory(targetCategory, session.session_id);
    [newStart, newEnd] = clampAgainstNeighbors(newStart, newEnd, neighbors, mode, origStartMin, origEndMin);

    dragState.newStartMin = newStart;
    dragState.newEndMin = newEnd;

    blockEl.style.left = `${(newStart / 1440) * 100}%`;
    blockEl.style.width = `${Math.max(0.25, ((newEnd - newStart) / 1440) * 100)}%`;
    blockEl.title = `${targetCategory}\n${displayTime(minutesToTimeString(ganttData.date, newStart))} → ${displayTime(minutesToTimeString(ganttData.date, newEnd))}`;
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
    const startMin = snapMinutes(laneMinutesFromEvent(lane, e.clientX));

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
    const currentMin = snapMinutes(laneMinutesFromEvent(lane, e.clientX));
    dragState.currentMin = currentMin;

    let lo = Math.min(startMin, currentMin);
    let hi = Math.max(startMin, currentMin);
    const neighbors = neighborRangesForCategory(lane.dataset.category, null);
    [lo, hi] = clampAgainstNeighbors(lo, hi, neighbors, startMin <= currentMin ? 'resize-right' : 'resize-left');

    dragState.clampedLo = lo;
    dragState.clampedHi = hi;
    draft.style.left = `${(lo / 1440) * 100}%`;
    draft.style.width = `${Math.max(0.25, ((hi - lo) / 1440) * 100)}%`;
}

function onLaneCreateEnd() {
    if (!dragState || dragState.mode !== 'create') return;
    const { lane, draft, clampedLo, clampedHi } = dragState;
    window.removeEventListener('mousemove', onLaneCreateMove);
    window.removeEventListener('mouseup', onLaneCreateEnd);
    draft.remove();
    dragState = null;

    const lo = clampedLo ?? 0;
    const hi = clampedHi ?? 0;
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
            errorEl.innerText = 'Invalid times — check the format (YYYY-MM-DD HH:MM:SS), that end is after start, and that it doesn\'t overlap another session in this category.';
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

function openSubtaskWindow() {
    const category = document.getElementById('subtask-window-category').value;
    if (!category) return;
    window.pywebview.api.open_subtask_window(category);
}

function resetCurrent() {
    if(confirm("Reset current session?")) window.pywebview.api.reset_timer();
}

let taskRows = [];
let categoriesWithHistory = new Set();

function renderTaskRows() {
    const list = document.getElementById('task-list');
    list.innerHTML = '';
    taskRows.forEach((name, i) => {
        const row = document.createElement('div');
        row.className = 'task-row';

        const input = document.createElement('input');
        input.type = 'text';
        input.value = name;
        input.oninput = () => { taskRows[i] = input.value; };

        const upBtn = document.createElement('button');
        upBtn.className = 'task-row-btn';
        upBtn.innerText = '↑';
        upBtn.disabled = i === 0;
        upBtn.onclick = () => moveTaskRow(i, -1);

        const downBtn = document.createElement('button');
        downBtn.className = 'task-row-btn';
        downBtn.innerText = '↓';
        downBtn.disabled = i === taskRows.length - 1;
        downBtn.onclick = () => moveTaskRow(i, 1);

        const delBtn = document.createElement('button');
        delBtn.className = 'task-row-btn delete-btn';
        delBtn.innerText = '×';
        delBtn.title = categoriesWithHistory.has(name) ? 'This task has recorded history — deleting it only hides it, past sessions are kept' : 'Delete';
        delBtn.onclick = () => removeTaskRow(i);

        row.appendChild(input);
        row.appendChild(upBtn);
        row.appendChild(downBtn);
        row.appendChild(delBtn);
        list.appendChild(row);
    });
}

function addTaskRow() {
    taskRows.push('');
    renderTaskRows();
    const inputs = document.querySelectorAll('#task-list input[type="text"]');
    if (inputs.length) inputs[inputs.length - 1].focus();
}

function moveTaskRow(i, direction) {
    const j = i + direction;
    if (j < 0 || j >= taskRows.length) return;
    [taskRows[i], taskRows[j]] = [taskRows[j], taskRows[i]];
    renderTaskRows();
}

function removeTaskRow(i) {
    taskRows.splice(i, 1);
    renderTaskRows();
}

function saveSettings() {
    const lines = taskRows.map(n => n.trim()).filter(n => n !== "");
    window.pywebview.api.update_config(lines).then(initUI);
    toggleSettings();
}

let catStep = 0;
const hub2 = document.getElementById('hub-2');
let hasSubtasksByCategory = {};
let latestActiveSubtask = null;
let latestActiveSubtask2 = null;

function categoryColor(catName) {
    const i = Math.max(0, cats.indexOf(catName) - 1);
    return chartColors[i % chartColors.length];
}

function hexToHsl(hex) {
    const r = parseInt(hex.slice(1, 3), 16) / 255;
    const g = parseInt(hex.slice(3, 5), 16) / 255;
    const b = parseInt(hex.slice(5, 7), 16) / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h = 0, s = 0;
    const l = (max + min) / 2;
    const d = max - min;
    if (d !== 0) {
        s = d / (1 - Math.abs(2 * l - 1));
        switch (max) {
            case r: h = ((g - b) / d) % 6; break;
            case g: h = (b - r) / d + 2; break;
            case b: h = (r - g) / d + 4; break;
        }
        h *= 60;
        if (h < 0) h += 360;
    }
    return { h: Math.round(h), s: Math.round(s * 100) };
}

function subtaskShade(baseHex, k, n) {
    const { h, s } = hexToHsl(baseHex);
    const l = n === 1 ? 53 : 38 + (30 * k) / (n - 1);
    return `hsl(${h} ${s}% ${l}%)`;
}

function annularArc(cx, cy, rIn, rOut, a0Deg, a1Deg) {
    const a0 = (a0Deg - 90) * Math.PI / 180;
    const a1 = (a1Deg - 90) * Math.PI / 180;
    const large = (a1Deg - a0Deg) > 180 ? 1 : 0;
    const p = (r, a) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
    const [x1, y1] = p(rOut, a0), [x2, y2] = p(rOut, a1);
    const [x3, y3] = p(rIn, a1), [x4, y4] = p(rIn, a0);
    return `M ${x1} ${y1} A ${rOut} ${rOut} 0 ${large} 1 ${x2} ${y2}`
         + ` L ${x3} ${y3} A ${rIn} ${rIn} 0 ${large} 0 ${x4} ${y4} Z`;
}

const ARC_R_IN = 51.5;
const ARC_R_OUT = 57.5;
const MIN_ARC_SEG_DEG = 4;
const NS = "http://www.w3.org/2000/svg";

function buildSubtaskArc(name, centerAngle, subs, isSecond) {
    const a0 = centerAngle - catStep / 2;
    const n = subs.length;
    const segDeg = catStep / (n + 1);
    const baseColor = categoryColor(name);
    const activeId = isSecond ? latestActiveSubtask2 : latestActiveSubtask;
    const hasSelection = !!activeId;

    const g = document.createElementNS(NS, "g");
    g.setAttribute("class", "subtask-arc");
    g.dataset.category = name;

    const collapsed = document.createElementNS(NS, "path");
    collapsed.setAttribute("d", annularArc(50, 50, ARC_R_IN, ARC_R_OUT, a0, a0 + catStep));
    collapsed.setAttribute("class", "arc-collapsed" + (hasSelection ? " has-selection" : ""));
    collapsed.setAttribute("fill", hasSelection ? baseColor : "#3a3a3a");
    g.appendChild(collapsed);

    const expanded = document.createElementNS(NS, "g");
    expanded.setAttribute("class", "arc-expanded");
    expanded.setAttribute("hidden", "hidden");

    if (segDeg < MIN_ARC_SEG_DEG) {
        // Too many subtasks for the arc to subdivide legibly: fall back to
        // a floating vertical list instead of unreadably thin slivers.
        collapsed.onclick = (e) => { e.stopPropagation(); openSubtaskPopover(name, subs, centerAngle, isSecond); };
        g.appendChild(expanded);
        return g;
    }

    let closeTimer = null;
    const expand = () => { clearTimeout(closeTimer); expanded.removeAttribute("hidden"); };
    const collapse = () => { closeTimer = setTimeout(() => expanded.setAttribute("hidden", "hidden"), 150); };
    g.addEventListener('mouseenter', expand);
    g.addEventListener('mouseleave', collapse);

    const options = [{ id: null, name: 'بدون زیرتسک' }, ...subs];
    options.forEach((opt, k) => {
        const segStart = a0 + segDeg * k;
        const seg = document.createElementNS(NS, "path");
        seg.setAttribute("d", annularArc(50, 50, ARC_R_IN, ARC_R_OUT, segStart, segStart + segDeg));
        const isSelected = opt.id === activeId;
        seg.setAttribute("class", "arc-seg" + (isSelected ? " selected" : ""));
        seg.setAttribute("fill", opt.id === null ? "#3a3a3a" : subtaskShade(baseColor, k - 1, subs.length));
        seg.dataset.subtask = opt.id || '';
        seg.onclick = (e) => {
            e.stopPropagation();
            setActiveSubtask(isSelected ? null : opt.id, isSecond);
        };
        seg.addEventListener('mouseenter', () => showSubtaskTooltip(seg, opt.name, segStart + segDeg / 2));
        seg.addEventListener('mouseleave', hideSubtaskTooltip);
        expanded.appendChild(seg);
    });

    g.appendChild(expanded);
    return g;
}

function showSubtaskTooltip(seg, name, angleDeg) {
    hideSubtaskTooltip();
    const rad = (angleDeg - 90) * Math.PI / 180;
    const tooltip = document.createElement('div');
    tooltip.className = 'subtask-tooltip';
    tooltip.id = 'subtask-tooltip';
    tooltip.innerText = name;
    const midR = (ARC_R_IN + ARC_R_OUT) / 2;
    // svg viewBox is -8..108 mapped over the container's pixel box (520px, minus 16px margin scaled)
    const px = (50 + midR * Math.cos(rad) + 8) / 116 * 520;
    const py = (50 + midR * Math.sin(rad) + 8) / 116 * 520;
    tooltip.style.left = px + 'px';
    tooltip.style.top = py + 'px';
    document.getElementById('app-ui').appendChild(tooltip);
}

function hideSubtaskTooltip() {
    const el = document.getElementById('subtask-tooltip');
    if (el) el.remove();
}

function openSubtaskPopover(name, subs, centerAngle, isSecond) {
    closeSubtaskPopover();
    const activeId = isSecond ? latestActiveSubtask2 : latestActiveSubtask;
    const rad = (centerAngle - 90) * Math.PI / 180;
    const popover = document.createElement('div');
    popover.className = 'subtask-popover';
    popover.id = 'subtask-popover';
    const px = (50 + 70 * Math.cos(rad) + 8) / 116 * 520;
    const py = (50 + 70 * Math.sin(rad) + 8) / 116 * 520;
    popover.style.left = px + 'px';
    popover.style.top = py + 'px';

    const options = [{ id: null, name: 'بدون زیرتسک' }, ...subs];
    options.forEach(opt => {
        const item = document.createElement('div');
        item.className = 'subtask-popover-item' + (opt.id === activeId ? ' selected' : '');
        item.innerText = opt.name;
        item.onclick = () => {
            setActiveSubtask(opt.id === activeId ? null : opt.id, isSecond);
            closeSubtaskPopover();
        };
        popover.appendChild(item);
    });

    document.getElementById('app-ui').appendChild(popover);
    setTimeout(() => document.addEventListener('click', closeSubtaskPopoverOnOutsideClick, { capture: true }), 0);
}

function closeSubtaskPopoverOnOutsideClick(e) {
    const popover = document.getElementById('subtask-popover');
    if (popover && !popover.contains(e.target)) closeSubtaskPopover();
}

function closeSubtaskPopover() {
    const el = document.getElementById('subtask-popover');
    if (el) el.remove();
    document.removeEventListener('click', closeSubtaskPopoverOnOutsideClick, { capture: true });
}

function setActiveSubtask(subtaskId, isSecond) {
    window.pywebview.api.set_active_subtask(subtaskId, !!isSecond).then(() => {
        refreshSubtaskArcs();
    });
}

function refreshSubtaskArcs() {
    window.pywebview.api.get_active_subtask().then(sel => {
        latestActiveSubtask = sel.active;
        latestActiveSubtask2 = sel.active_2;
        renderSubtaskArcs();
    });
}

let latestActiveCat = null, latestActiveCat2 = null;

function renderSubtaskArcs() {
    document.querySelectorAll('.subtask-arc').forEach(e => e.remove());
    hideSubtaskTooltip();
    closeSubtaskPopover();

    const activeLabel = document.getElementById('active-subtask-label');
    activeLabel.style.display = 'none';

    if (latestActiveCat && hasSubtasksByCategory[latestActiveCat]) {
        window.pywebview.api.get_subtasks(latestActiveCat).then(subs => {
            if (subs.length === 0) return;
            const idx = cats.indexOf(latestActiveCat);
            const g = buildSubtaskArc(latestActiveCat, idx * catStep, subs, false);
            svg.appendChild(g);

            const active = subs.find(s => s.id === latestActiveSubtask);
            if (active) {
                activeLabel.innerText = active.name;
                activeLabel.style.display = 'block';
            }
        });
    }
    if (latestActiveCat2 && hasSubtasksByCategory[latestActiveCat2]) {
        window.pywebview.api.get_subtasks(latestActiveCat2).then(subs => {
            if (subs.length === 0) return;
            const idx2 = cats.indexOf(latestActiveCat2);
            const g = buildSubtaskArc(latestActiveCat2, idx2 * catStep, subs, true);
            svg.appendChild(g);
        });
    }
}

function initUI(data) {
    cats = data.categories;
    hasSubtasksByCategory = data.has_subtasks || {};
    latestActiveSubtask = data.active_subtask || null;
    latestActiveSubtask2 = data.active_subtask_2 || null;
    svg.innerHTML = '';
    document.querySelectorAll('.label').forEach(e => e.remove());
    catStep = 360 / cats.length;
    cats.forEach((name, i) => {
        const centerAngle = i * catStep;
        const sRad = (centerAngle - catStep/2 - 90) * Math.PI / 180, eRad = (centerAngle + catStep/2 - 90) * Math.PI / 180;
        const x1 = 50 + 50 * Math.cos(sRad), y1 = 50 + 50 * Math.sin(sRad), x2 = 50 + 50 * Math.cos(eRad), y2 = 50 + 50 * Math.sin(eRad);
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", `M 50 50 L ${x1} ${y1} A 50 50 0 0 1 ${x2} ${y2} Z`);
        path.setAttribute("class", "slice");
        path.onclick = (e) => select(name, e.ctrlKey || e.metaKey);
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
    applyActiveState(data.active, data.active_2);
}

window.addEventListener('pywebviewready', () => window.pywebview.api.get_init_data().then(initUI));

// Reflects backend truth on the wheel: primary needle/label always shown,
// second needle/label/readout only shown while a second task is running.
function applyActiveState(active, active2) {
    const activeIdx = cats.indexOf(active);
    hub.style.transform = `rotate(${activeIdx * catStep}deg)`;

    document.querySelectorAll('.label').forEach(l => l.classList.remove('active', 'active-2'));
    if (document.getElementById('lbl-' + active)) document.getElementById('lbl-' + active).classList.add('active');

    const secondBox = document.getElementById('second-task-box');
    if (active2) {
        const idx2 = cats.indexOf(active2);
        hub2.style.transform = `rotate(${idx2 * catStep}deg)`;
        hub2.style.display = 'block';
        secondBox.style.display = 'flex';
        if (document.getElementById('lbl-' + active2)) document.getElementById('lbl-' + active2).classList.add('active-2');
    } else {
        hub2.style.display = 'none';
        secondBox.style.display = 'none';
    }

    const categoryChanged = active !== latestActiveCat || active2 !== latestActiveCat2;
    latestActiveCat = active;
    latestActiveCat2 = active2;
    if (categoryChanged) {
        refreshSubtaskArcs();
    }
}

function select(name, asSecond) {
    window.pywebview.api.set_category(name, !!asSecond).then(() => {
        window.pywebview.api.get_status().then(s => applyActiveState(s.active, s.active_2));
    });
}

setInterval(() => {
    if(window.pywebview.api) {
        window.pywebview.api.get_status().then(s => {
            document.getElementById('session-time').innerText = format(s.session);
            document.getElementById('total-time').innerText = format(s.total, true);
            if (s.active_2) {
                document.getElementById('second-task-name').innerText = s.active_2.toUpperCase();
                document.getElementById('second-task-time').innerText = format(s.session_2);
            }
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
