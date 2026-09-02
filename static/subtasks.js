const params = new URLSearchParams(window.location.search);
const category = params.get('category') || '';
document.getElementById('page-title').innerText = 'SUBTASKS — ' + category;

let subRows = [];          // working copy of {id, name, planned_start, planned_end}
let subGanttOffset = 0;

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

function addDays(date, days) {
    const d = new Date(date);
    d.setDate(d.getDate() + days);
    return d;
}

function secondsToLabel(s) {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${h}h ${m}m`;
}

function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
    if (name === 'gantt') loadSubGantt();
    if (name === 'plan') loadPlanTable();
}

// ---------------- List tab ----------------

function loadSubList() {
    window.pywebview.api.get_subtasks(category).then(subs => {
        subRows = subs;
        renderSubRows();
    });
}

function renderSubRows() {
    const list = document.getElementById('sub-list');
    list.innerHTML = '';
    subRows.forEach((s, i) => {
        const row = document.createElement('div');
        row.className = 'sub-row';

        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.value = s.name;
        nameInput.onchange = () => saveSubField(s.id, 'name', nameInput.value);

        const startInput = document.createElement('input');
        startInput.type = 'text';
        startInput.className = 'date-field';
        startInput.readOnly = true;
        startInput.placeholder = 'start';
        startInput.value = s.planned_start ? gregorianStrToJalaliStr(s.planned_start) : '';
        startInput.id = 'plan-start-' + s.id;
        startInput.onclick = () => openJalaliPicker(startInput.id, v => saveSubField(s.id, 'planned_start', jalaliStrToGregorianStr(v)));

        const endInput = document.createElement('input');
        endInput.type = 'text';
        endInput.className = 'date-field';
        endInput.readOnly = true;
        endInput.placeholder = 'end';
        endInput.value = s.planned_end ? gregorianStrToJalaliStr(s.planned_end) : '';
        endInput.id = 'plan-end-' + s.id;
        endInput.onclick = () => openJalaliPicker(endInput.id, v => saveSubField(s.id, 'planned_end', jalaliStrToGregorianStr(v)));

        const upBtn = document.createElement('button');
        upBtn.className = 'row-btn';
        upBtn.innerText = '↑';
        upBtn.disabled = i === 0;
        upBtn.onclick = () => moveSubRow(i, -1);

        const downBtn = document.createElement('button');
        downBtn.className = 'row-btn';
        downBtn.innerText = '↓';
        downBtn.disabled = i === subRows.length - 1;
        downBtn.onclick = () => moveSubRow(i, 1);

        const archiveBtn = document.createElement('button');
        archiveBtn.className = 'row-btn archive-btn';
        archiveBtn.innerText = '×';
        archiveBtn.title = 'Archive';
        archiveBtn.onclick = () => archiveSubRow(s.id);

        row.appendChild(nameInput);
        row.appendChild(startInput);
        row.appendChild(endInput);
        row.appendChild(upBtn);
        row.appendChild(downBtn);
        row.appendChild(archiveBtn);
        list.appendChild(row);
    });
}

function saveSubField(id, field, value) {
    const args = { id: null, name: null, planned_start: null, planned_end: null, color: null };
    args[field] = value;
    window.pywebview.api.update_subtask(id, args.name, args.planned_start, args.planned_end, args.color)
        .then(() => loadSubList());
}

function addSubRow() {
    const name = prompt('Subtask name:');
    if (!name || !name.trim()) return;
    window.pywebview.api.create_subtask(category, name.trim()).then(() => loadSubList());
}

function moveSubRow(i, direction) {
    const j = i + direction;
    if (j < 0 || j >= subRows.length) return;
    [subRows[i], subRows[j]] = [subRows[j], subRows[i]];
    renderSubRows();
    window.pywebview.api.reorder_subtasks(category, subRows.map(s => s.id));
}

function archiveSubRow(id) {
    if (!confirm('Archive this subtask? Past sessions keep their label.')) return;
    window.pywebview.api.archive_subtask(id).then(() => loadSubList());
}

// ---------------- Gantt tab ----------------

function shiftSubGanttDay(direction) {
    subGanttOffset = direction === 0 ? 0 : subGanttOffset + direction;
    loadSubGantt();
}

function timeToTimelineMinutes(dateTimeText) {
    const timePart = dateTimeText.split(' ')[1] || '00:00:00';
    const parts = timePart.split(':').map(Number);
    const totalMinutes = parts[0] * 60 + parts[1] + (parts[2] || 0) / 60;
    return (totalMinutes - 360 + 1440) % 1440;
}

function displayTime(dateTimeText) {
    return (dateTimeText.split(' ')[1] || '00:00:00').slice(0, 5);
}

const subChartColors = [
    "#00e5ff", "#ff4b2b", "#ffd166", "#06d6a0", "#9b5de5",
    "#f15bb5", "#fee440", "#00bbf9", "#f77f00", "#80ed99"
];

function loadSubGantt() {
    const targetDate = logicalDateString(addDays(new Date(), subGanttOffset));
    window.pywebview.api.get_subtask_gantt(category, targetDate).then(data => {
        document.getElementById('sub-gantt-date').innerText = gregorianStrToJalaliStr(data.date);
        renderSubGantt(data);
    });
}

function renderSubGantt(data) {
    const chart = document.getElementById('sub-gantt-chart');
    chart.innerHTML = '';

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

    const rows = data.rows || [];
    const sessions = data.sessions || [];

    if (sessions.length === 0) {
        chart.innerHTML += '<div class="gantt-empty">No sessions for this day yet.</div>';
        return;
    }

    rows.forEach((row, i) => {
        const rowSessions = sessions.filter(s => (s.subtask_id || null) === row.id);
        if (rowSessions.length === 0) return;

        const rowEl = document.createElement('div');
        rowEl.className = 'gantt-row';

        const label = document.createElement('div');
        label.className = 'gantt-label';
        label.innerText = row.name;
        label.title = row.name;

        const lane = document.createElement('div');
        lane.className = 'gantt-lane';

        rowSessions.forEach(s => {
            const startMin = Math.max(0, Math.min(1440, timeToTimelineMinutes(s.start)));
            let endMin = Math.max(0, Math.min(1440, timeToTimelineMinutes(s.end)));
            if (endMin <= startMin) endMin = 1440;
            const block = document.createElement('div');
            block.className = 'gantt-block' + (s.live ? ' live' : '');
            block.style.left = `${(startMin / 1440) * 100}%`;
            block.style.width = `${Math.max(0.25, ((endMin - startMin) / 1440) * 100)}%`;
            block.style.background = subChartColors[i % subChartColors.length];
            block.title = `${row.name}\n${displayTime(s.start)} → ${displayTime(s.end)}${s.live ? ' / live' : ''}`;
            lane.appendChild(block);
        });

        rowEl.appendChild(label);
        rowEl.appendChild(lane);
        chart.appendChild(rowEl);
    });
}

// ---------------- Range stats tab ----------------

function loadSubRangeStats() {
    const startJalali = document.getElementById('sub-range-start').value;
    const endJalali = document.getElementById('sub-range-end').value;
    const result = document.getElementById('sub-range-result');
    if (!startJalali || !endJalali) {
        result.innerText = 'اول و آخر بازه رو انتخاب کن.';
        return;
    }
    const start = jalaliStrToGregorianStr(startJalali);
    const end = jalaliStrToGregorianStr(endJalali);

    window.pywebview.api.get_subtask_range_report(category, start, end).then(report => {
        result.innerHTML = '';
        const nameById = { null: 'بدون زیرتسک' };
        subRows.forEach(s => { nameById[s.id] = s.name; });

        Object.entries(report.totals).forEach(([id, seconds]) => {
            if (!seconds) return;
            const row = document.createElement('div');
            row.className = 'stats-result-row';
            const key = id === 'null' || id === 'None' ? null : id;
            row.innerHTML = `<span>${nameById[key] || nameById[id] || 'بدون زیرتسک'}</span><span>${secondsToLabel(seconds)}</span>`;
            result.appendChild(row);
        });
    });
}

// ---------------- Planned vs actual tab ----------------

function loadPlanTable() {
    window.pywebview.api.get_subtask_summary(category).then(rows => {
        const tbody = document.getElementById('plan-tbody');
        tbody.innerHTML = rows.map(r => `
            <tr>
                <td>${r.name}</td>
                <td>${r.planned_start ? gregorianStrToJalaliStr(r.planned_start) : '—'} → ${r.planned_end ? gregorianStrToJalaliStr(r.planned_end) : '—'}</td>
                <td>${secondsToLabel(r.spent)}</td>
                <td>${r.last_activity || '—'}</td>
            </tr>
        `).join('');
    });
}

// ---------------- Jalali picker (adapted from app.js) ----------------

let jalaliPickerTarget = null;
let jalaliPickerYear = null;
let jalaliPickerMonth = null;
let jalaliPickerOnPick = null;

function openJalaliPicker(inputId, onPick) {
    const input = document.getElementById(inputId);
    const picker = document.getElementById('jalali-picker');
    jalaliPickerTarget = inputId;
    jalaliPickerOnPick = onPick || null;

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
    const jsWeekday = jsDate.getDay();
    const firstCellOffset = (jsWeekday + 1) % 7;

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
    if (jalaliPickerOnPick) jalaliPickerOnPick(dayStr);
}

window.addEventListener('pywebviewready', () => {
    loadSubList();
    const todayJalali = gregorianStrToJalaliStr(localDateString(new Date()));
    document.getElementById('sub-range-start').value = todayJalali;
    document.getElementById('sub-range-end').value = todayJalali;
});
