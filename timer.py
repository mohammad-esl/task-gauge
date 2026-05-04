import webview
import time
import os
import json
import csv
from datetime import datetime, timedelta

class TimerApi:
    def __init__(self):
        self.log_file = "timer_history.txt"
        self.config_file = "config.json"
        self.report_file = "daily_report.csv"
        self.last_report_save = time.time()
        self.report_save_interval = 300  # 5 minutes
        
        # Default data
        self.data = {
            "categories": ["Nothing", "Education", "Work", "Study", "Project 1"],
            "totals": {"Nothing": 0, "Education": 0, "Work": 0, "Study": 0, "Project 1": 0},
            "last_date": datetime.now().strftime("%Y-%m-%d")
        }
        
        self.load_config()
        self._check_daily_reset()
        
        # Force "Nothing" to exist
        if "Nothing" not in self.data["categories"]:
            self.data["categories"].insert(0, "Nothing")
        if "Nothing" not in self.data["totals"]:
            self.data["totals"]["Nothing"] = 0
            
        self.active_cat = "Nothing"
        self.start_time = time.time()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    self.data = json.load(f)
            except: pass

        if "last_date" not in self.data:
            self.data["last_date"] = datetime.now().strftime("%Y-%m-%d")

    def save_config(self):
        with open(self.config_file, "w") as f:
            json.dump(self.data, f)

    def _get_live_totals(self):
        totals = self.data["totals"].copy()

        if hasattr(self, "active_cat") and hasattr(self, "start_time"):
            session = int(time.time() - self.start_time)
            totals[self.active_cat] = totals.get(self.active_cat, 0) + session

        return totals

    def _format_hms(self, seconds):
        h, m, s = self._get_hms(seconds)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _save_daily_report(self, date_str):
        totals = self._get_live_totals()
        rows = []
        fieldnames = ["date"] + self.data["categories"]

        if os.path.exists(self.report_file):
            with open(self.report_file, "r", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                for field in reader.fieldnames or []:
                    if field not in fieldnames:
                        fieldnames.append(field)

        existing = {row["date"]: row for row in rows if "date" in row}

        row = {"date": date_str}
        for cat in fieldnames:
            if cat == "date":
                continue
            row[cat] = self._format_hms(totals.get(cat, 0))

        existing[date_str] = row

        with open(self.report_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(existing.values())

    def get_today_report(self):
        self._check_daily_reset()
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "totals": self._get_live_totals()
        }

    def save_today_report(self):
        today = datetime.now().strftime("%Y-%m-%d")
        self._save_daily_report(today)
        return {"status": "saved"}

    def get_week_report(self, week_offset=0):
        self._save_daily_report(datetime.now().strftime("%Y-%m-%d"))

        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_week = start_of_week + timedelta(weeks=int(week_offset))
        end_of_week = start_of_week + timedelta(days=6)

        rows = {}
        if os.path.exists(self.report_file):
            with open(self.report_file, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows[row["date"]] = row

        days = []
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            date_str = day.strftime("%Y-%m-%d")
            row = rows.get(date_str, {})

            totals = {}
            for cat in self.data["categories"]:
                value = row.get(cat, "00:00:00")
                try:
                    h, m, s = [int(x) for x in value.split(":")]
                    totals[cat] = h * 3600 + m * 60 + s
                except:
                    totals[cat] = 0

            days.append({
                "date": date_str,
                "label": day.strftime("%a"),
                "totals": totals
            })

        return {
            "week_start": start_of_week.strftime("%Y-%m-%d"),
            "week_end": end_of_week.strftime("%Y-%m-%d"),
            "categories": self.data["categories"],
            "days": days
        }

    def _check_daily_reset(self):
        today = datetime.now().date()
        last = datetime.strptime(self.data["last_date"], "%Y-%m-%d").date()

        if today != last:
            self._save_daily_report(self.data["last_date"])

            self.data["totals"] = {k: 0 for k in self.data["categories"]}
            self.data["last_date"] = today.strftime("%Y-%m-%d")

            with open(self.log_file, "a") as f:
                f.write(f"\n--- NEW DAY: {self.data['last_date']} ---\n")

            self.save_config()

    def _get_hms(self, s):
        return s // 3600, (s % 3600) // 60, s % 60

    def _write_to_history(self, name, session_duration):
        # We log "Nothing" to history only if it was a significant "break" (> 10 seconds)
        if session_duration < 10: return 
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        sh, sm, ss = self._get_hms(session_duration)
        th, tm, ts = self._get_hms(self.data["totals"].get(name, 0))
        
        prefix = "[BREAK]   " if name == "Nothing" else "[TASK]    "
        log_entry = (f"{timestamp} | {prefix} {name.ljust(15)} | "
                     f"Session: {sh}h {sm}m {ss}s | Total: {th}h {tm}m {ts}s\n")
        
        with open(self.log_file, "a") as f:
            f.write(log_entry)

    def get_init_data(self):
        # Now "Nothing" is included in the history list for the Dashboard
        history_list = [{"name": k, "time": f"{h}h {m}m {s}s"} 
                       for k, v in self.data["totals"].items() 
                       for h, m, s in [self._get_hms(v)]]
        return {"categories": self.data["categories"], "active": self.active_cat, "history": history_list}

    def set_category(self, name):
        self._check_daily_reset()

        now = time.time()
        duration = int(now - self.start_time)
        
        # Always update totals and save
        self.data["totals"][self.active_cat] += duration
        self._write_to_history(self.active_cat, duration)
        self.save_config()
        
        self.active_cat = name
        self.start_time = now

        self._save_daily_report(datetime.now().strftime("%Y-%m-%d"))
        self.last_report_save = time.time()

        return {"status": "success"}

    def reset_timer(self):
        self.start_time = time.time()
        return {"status": "reset"}

    def update_config(self, new_cats):
        self.set_category(self.active_cat)
        
        # Ensure Nothing stays at index 0
        if "Nothing" in new_cats: new_cats.remove("Nothing")
        new_cats.insert(0, "Nothing")
            
        new_totals = {name: self.data["totals"].get(name, 0) for name in new_cats}
        self.data["categories"], self.data["totals"] = new_cats, new_totals
        
        self.active_cat = "Nothing"
        self.start_time = time.time()
        self.save_config()
        self._save_daily_report(datetime.now().strftime("%Y-%m-%d"))
        return self.get_init_data()

    def get_status(self):
        self._check_daily_reset()

        if time.time() - self.last_report_save >= self.report_save_interval:
            self._save_daily_report(datetime.now().strftime("%Y-%m-%d"))
            self.last_report_save = time.time()

        now = time.time()
        session = int(now - self.start_time)
        return {
            "active": self.active_cat,
            "session": session,
            "total": self.data["totals"].get(self.active_cat, 0) + session
        }

html_content = """
<!DOCTYPE html>
<html>
<head>
    <style>
        :root { --bg: #0a0a0a; --accent: #00e5ff; --ring: #161616; --red: #ff4b2b; }
        body { background: var(--bg); color: white; font-family: 'Segoe UI', sans-serif; 
               display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; overflow: hidden; }
        .main-container { position: relative; width: 480px; height: 480px; transition: filter 0.3s; }
        .blur { filter: blur(15px); pointer-events: none; }
        #hit-surface { position: absolute; width: 100%; height: 100%; z-index: 5; }
        .slice { fill: var(--ring); stroke: #222; stroke-width: 1; cursor: pointer; transition: fill 0.2s; }
        .slice:hover { fill: #222; }
        #hub { position: absolute; width: 100%; height: 100%; z-index: 6; pointer-events: none; transition: transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1); }
        .needle { position: absolute; top: 15px; left: 50%; transform: translateX(-50%); width: 4px; height: 40px; background: var(--accent); box-shadow: 0 0 15px var(--accent); border-radius: 2px; }
        .label { position: absolute; width: 100px; text-align: center; font-weight: bold; font-size: 11px; color: #444; z-index: 7; pointer-events: none; text-transform: uppercase; }
        .label.active { color: var(--accent); text-shadow: 0 0 10px var(--accent); }
        .center-display { position: absolute; width: 280px; height: 280px; background: #000; border-radius: 50%; top: 50%; left: 50%; transform: translate(-50%, -50%); border: 10px solid #222; z-index: 10; display: flex; flex-direction: column; justify-content: center; align-items: center; }
        #session-time { font-size: 68px; color: var(--accent); font-family: monospace; line-height: 1; cursor: pointer; }
        .total-box { color: #888; font-family: monospace; font-size: 13px; background: #111; padding: 4px 12px; border-radius: 15px; border: 1px solid #222;}
        .controls { margin-top: 15px; display: flex; gap: 8px; }
        .icon-btn { background: none; border: 1px solid #333; color: #555; cursor: pointer; padding: 4px 8px; border-radius: 4px; font-size: 10px; }
        .icon-btn:hover { color: white; border-color: #777; }
        #settings-panel { position: absolute; width: 380px; background: rgba(15,15,15,0.98); border: 1px solid #333; padding: 20px; border-radius: 15px; z-index: 100; display: none; box-shadow: 0 0 50px black; max-height: 90vh; overflow-y: auto; }
        textarea { width: 100%; height: 80px; background: #000; color: var(--accent); border: 1px solid #444; padding: 8px; box-sizing: border-box; margin-bottom: 15px; }
        .stats-table { width: 100%; font-size: 11px; border-collapse: collapse; margin-bottom: 15px; color: #aaa; }
        .stats-table td { padding: 4px 0; border-bottom: 1px solid #222; }
        .stats-table tr td:last-child { text-align: right; color: var(--accent); }
        .save-btn { background: var(--accent); color: black; border: none; padding: 10px; width: 100%; cursor: pointer; font-weight: bold; border-radius: 4px; margin-top: 5px; }
        #week-chart { height: 180px; display: flex; align-items: flex-end; gap: 8px; border-bottom: 1px solid #333; padding-bottom: 8px; margin-bottom: 12px; }
        .bar-wrapper { flex: 1; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; }
        .bar { width: 100%; display: flex; flex-direction: column-reverse; background: #111; border: 1px solid #222; box-sizing: border-box; }
        .bar-label { font-size: 10px; color: #777; margin-top: 4px; }
        .legend { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; font-size: 10px; color: #aaa; }
        .legend-item { display: flex; align-items: center; gap: 4px; }
        .legend-dot { width: 8px; height: 8px; border-radius: 2px; }
    </style>
</head>
<body>
    <div id="settings-panel">
        <h4 style="margin:0 0 10px 0; color:var(--accent); letter-spacing:1px">DASHBOARD</h4>
        <table class="stats-table" id="history-table"></table>

        <h5 style="margin:10px 0 5px 0; font-size:10px; color:#555">WEEKLY VIEW</h5>
        <div style="display:flex; gap:6px; margin-bottom:10px;">
            <button class="icon-btn" onclick="changeWeek(-1)">← PREV</button>
            <button class="icon-btn" onclick="changeWeek(0)">THIS WEEK</button>
            <button class="icon-btn" onclick="changeWeek(1)">NEXT →</button>
        </div>

        <div id="week-label" style="font-size:11px; color:#777; margin-bottom:8px;"></div>
        <div id="week-chart"></div>
        <div id="week-legend" class="legend"></div>

        <h5 style="margin:10px 0 5px 0; font-size:10px; color:#555">EDIT TASKS (One per line)</h5>
        <textarea id="cat-input" placeholder="Enter tasks..."></textarea>
        <button class="save-btn" onclick="saveSettings()">APPLY CHANGES</button>
        <button class="save-btn" style="background:#222; color:#777" onclick="toggleSettings()">CLOSE</button>
    </div>

    <div class="main-container" id="app-ui">
        <svg id="hit-surface" viewBox="0 0 100 100"></svg>
        <div id="hub"><div class="needle"></div></div>
        <div class="center-display">
            <div id="session-time" onclick="toggleSettings()">00:00</div>
            <div class="total-box">TOTAL <span id="total-time">00:00:00</span></div>
            <div class="controls">
                <button class="icon-btn" onclick="toggleSettings()">STATS/EDIT</button>
                <button class="icon-btn" onclick="resetCurrent()" style="color:var(--red)">RESET</button>
            </div>
        </div>
    </div>

    <script>
        let cats = [];
        let currentWeekOffset = 0;
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
                        segment.title = `${cat}: ${secondsToLabel(seconds)}`;
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
            const ui = document.getElementById('app-ui');
            const isVisible = panel.style.display === 'block';
            if (!isVisible) {
                window.pywebview.api.get_init_data().then(data => {
                    const table = document.getElementById('history-table');
                    table.innerHTML = data.history.map(h => `<tr><td>${h.name}</td><td>${h.time}</td></tr>`).join('');
                    document.getElementById('cat-input').value = data.categories.filter(c => c !== "Nothing").join('\\n');
                    loadWeekChart();
                });
            }
            panel.style.display = isVisible ? 'none' : 'block';
            ui.className = isVisible ? 'main-container' : 'main-container blur';
        }

        function resetCurrent() { if(confirm("Reset current session?")) window.pywebview.api.reset_timer(); }

        function saveSettings() {
            const lines = document.getElementById('cat-input').value.split('\\n').filter(l => l.trim() !== "");
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
                label.className = 'label'; label.id = 'lbl-' + name; label.innerText = name;
                const rad = (centerAngle - 90) * (Math.PI / 180);
                label.style.left = (240 + 195 * Math.cos(rad) - 50) + 'px';
                label.style.top = (240 + 195 * Math.sin(rad) - 10) + 'px';
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
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    api = TimerApi()
    window = webview.create_window('Task Gauge Pro', html=html_content, js_api=api, width=540, height=600, resizable=False)
    webview.start(gui='edgechromium')