(function () {
    'use strict';

    const PLUGIN_ID = 'retune';
    const ACTION_ID = 'retune.convert';
    const PREVIEW_DELAY_MS = 250;
    const hooks = window.__feedBackRetune || (window.__feedBackRetune = {});

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function semitones(n) {
        const abs = Math.abs(n);
        return `${n > 0 ? 'up' : 'down'} ${abs} semitone${abs === 1 ? '' : 's'}`;
    }

    function audioChange(n) {
        return n ? `audio ${semitones(n)}` : 'no audio change';
    }

    function chartSummary(chart) {
        if (!chart || !chart.refretted) return 'Frets stay the same — only the tuning changes.';
        const parts = [`${chart.refretted} note${chart.refretted === 1 ? '' : 's'} re-fretted`];
        if (chart.relocated) parts.push(`${chart.relocated} moved to another string`);
        if (chart.octave_moved) parts.push(`${chart.octave_moved} moved up an octave (below the lowest string)`);
        if (chart.removed) parts.push(`${chart.removed} unplayable and removed`);
        if (chart.slides_cleared) parts.push(`${chart.slides_cleared} slide${chart.slides_cleared === 1 ? '' : 's'} dropped`);
        if (chart.harmonics_moved) parts.push(`${chart.harmonics_moved} harmonic${chart.harmonics_moved === 1 ? '' : 's'} on a moved fret`);
        return parts.join(' · ');
    }

    function targetLabel(t) {
        return t.keep ? `${t.name} — no audio change (change strings only)` : `${t.name} — ${audioChange(t.shift)}`;
    }

    function groupFor(t) {
        if (t.keep) return 'Current';
        if (t.family === 'standard') return 'Standard';
        if (t.family === 'drop') return 'Drop';
        return 'Shifted';
    }

    function openModal(song) {
        closeModal();
        const overlay = el('div', 'plugin-retune-overlay');
        overlay.id = 'plugin-retune-modal';
        const card = el('div', 'plugin-retune-card');
        card.setAttribute('role', 'dialog');
        card.setAttribute('aria-modal', 'true');
        card.setAttribute('aria-labelledby', 'plugin-retune-title');
        const title = el('h3', 'plugin-retune-title', 'Retune song');
        title.id = 'plugin-retune-title';
        const subtitle = el('p', 'plugin-retune-sub', [song.artist, song.title].filter(Boolean).join(' — ') || song.filename);
        const body = el('div', 'plugin-retune-body');
        body.appendChild(el('p', 'plugin-retune-dim', 'Loading tunings…'));
        card.append(title, subtitle, body);
        overlay.appendChild(card);
        overlay.addEventListener('click', (e) => { if (e.target === overlay && !hooks.busy) closeModal(); });
        document.body.appendChild(overlay);
        hooks.onKey = (e) => { if (e.key === 'Escape' && !hooks.busy) closeModal(); };
        document.addEventListener('keydown', hooks.onKey);
        return body;
    }

    function closeModal() {
        document.getElementById('plugin-retune-modal')?.remove();
        if (hooks.onKey) document.removeEventListener('keydown', hooks.onKey);
        hooks.onKey = null;
        hooks.busy = false;
    }

    function buttons(...specs) {
        const row = el('div', 'plugin-retune-actions');
        for (const [label, cls, onClick] of specs) {
            const b = el('button', `plugin-retune-btn ${cls}`, label);
            b.type = 'button';
            b.addEventListener('click', onClick);
            row.appendChild(b);
        }
        return row;
    }

    function showError(body, message) {
        body.replaceChildren(el('p', 'plugin-retune-error', message), buttons(['Close', 'plugin-retune-btn-ghost', closeModal]));
    }

    async function run(song) {
        const body = openModal(song);
        let options;
        try {
            const r = await fetch(`/api/plugins/${PLUGIN_ID}/options?filename=${encodeURIComponent(song.filename)}`);
            const text = await r.text();
            try { options = JSON.parse(text); } catch (_) { options = null; }
            if (!r.ok || !options) throw new Error((options && options.detail) || `HTTP ${r.status}`);
        } catch (e) {
            showError(body, `Could not read this song: ${e.message}`);
            return;
        }
        renderPicker(body, song, options);
    }

    function hasStringChoices(options) {
        return (options.arrangements || []).some((a) => a.choices && a.choices.length > 1);
    }

    function defaultTarget(options) {
        if (hasStringChoices(options)) return String(Math.max(0, options.targets.findIndex((t) => t.keep)));
        const usable = options.targets
            .map((t, i) => ({ t, i }))
            .filter(({ t }) => !t.keep && (!t.shift || options.ffmpeg));
        const estd = usable.find(({ t }) => t.name === 'E Standard');
        if (estd) return String(estd.i);
        usable.sort((a, b) => (Math.abs(a.t.shift) + (a.t.low_adjust ? 0.5 : 0))
            - (Math.abs(b.t.shift) + (b.t.low_adjust ? 0.5 : 0)));
        return usable.length ? String(usable[0].i) : '';
    }

    function changeLines(report, prefix) {
        const lines = [];
        if (!report.chart || !report.chart.refretted) lines.push(el('p', '', `${prefix}${chartSummary(report.chart)}`));
        for (const a of report.arrangements || []) {
            if (a.from === a.to && !a.refretted) continue;
            const line = el('p', 'plugin-retune-change');
            line.append(el('strong', '', `${a.name}: `), `${a.from} → ${a.to}`);
            const effect = a.refretted ? chartSummary(a) : 'frets stay the same';
            line.append(el('span', 'plugin-retune-dim-inline', ` — ${effect}`));
            lines.push(line);
        }
        return lines;
    }

    function renderPicker(body, song, options) {
        const currentTuning = el('p', 'plugin-retune-current');
        currentTuning.append('Current tuning: ', el('strong', '', options.source.name));

        const select = el('select', 'plugin-retune-select');
        select.setAttribute('aria-label', 'Target tuning');
        const groups = new Map();
        const offerKeep = hasStringChoices(options);
        options.targets.forEach((t, i) => {
            if (t.keep && !offerKeep) return;
            const name = groupFor(t);
            if (!groups.has(name)) {
                const g = el('optgroup');
                g.label = name;
                groups.set(name, g);
                select.appendChild(g);
            }
            const opt = el('option', '', targetLabel(t));
            opt.value = String(i);
            opt.disabled = !!t.shift && !options.ffmpeg;
            groups.get(name).appendChild(opt);
        });
        select.value = defaultTarget(options);
        const selected = () => {
            const opt = select.selectedOptions[0];
            return opt && !opt.disabled ? options.targets[Number(opt.value)] : null;
        };

        const stringsBox = el('div', 'plugin-retune-strings');
        const stringSelects = [];
        for (const a of options.arrangements || []) {
            if (!a.choices || a.choices.length < 2) continue;
            const row = el('label', 'plugin-retune-string-row');
            row.append(el('span', '', `${a.name} strings`));
            const pick = el('select', 'plugin-retune-select plugin-retune-select-small');
            for (const n of a.choices) {
                const opt = el('option', '', n === a.strings ? `${n} (current)` : String(n));
                opt.value = String(n);
                pick.appendChild(opt);
            }
            pick.value = String(a.strings);
            row.append(pick);
            stringsBox.append(row);
            stringSelects.push({ arrangement: a, pick });
        }
        const changedStrings = () => {
            const counts = {};
            for (const { arrangement, pick } of stringSelects) {
                const n = Number(pick.value);
                if (n !== arrangement.strings) for (const id of arrangement.ids) counts[id] = n;
            }
            return counts;
        };

        let previewSeq = 0;
        let previewTimer = null;
        let previewAbort = null;
        let current = null;
        const detail = el('div', 'plugin-retune-detail');
        const describe = () => {
            const t = selected();
            const counts = changedStrings();
            const seq = ++previewSeq;
            current = null;
            convertButton.disabled = true;
            clearTimeout(previewTimer);
            if (previewAbort) previewAbort.abort();
            previewAbort = null;
            detail.replaceChildren();
            if (!t) return;
            if (t.keep && !Object.keys(counts).length) {
                detail.appendChild(el('p', 'plugin-retune-dim', 'Pick a target tuning or change a string count.'));
                return;
            }
            detail.appendChild(el('p', 'plugin-retune-dim', 'Checking the chart…'));
            previewTimer = setTimeout(() => showPreview(t, counts, seq), PREVIEW_DELAY_MS);
        };
        const showPreview = async (t, counts, seq) => {
            previewAbort = new AbortController();
            let preview;
            try {
                const qs = new URLSearchParams({
                    filename: song.filename, shift: t.shift, low_adjust: t.low_adjust, strings: JSON.stringify(counts),
                });
                const r = await fetch(`/api/plugins/${PLUGIN_ID}/preview?${qs}`, { signal: previewAbort.signal });
                const text = await r.text();
                try { preview = JSON.parse(text); } catch (_) { preview = null; }
                if (!r.ok || !preview) throw new Error((preview && preview.detail) || `HTTP ${r.status}`);
            } catch (e) {
                if (seq !== previewSeq) return;
                detail.replaceChildren(el('p', 'plugin-retune-error', e.message));
                return;
            }
            if (seq !== previewSeq) return;
            current = { target: t, counts, preview };
            convertButton.disabled = false;
            detail.replaceChildren(
                el('p', '', t.shift ? `Audio: pitch-shifted ${semitones(t.shift)}.` : 'Audio: unchanged.'),
            );
            detail.append(...changeLines(preview, 'Chart: '));
            const restandardised = (preview.arrangements || []).some((a) => a.strings_to > a.strings_from && a.from !== a.to);
            if (t.keep && restandardised) {
                detail.appendChild(el('p', 'plugin-retune-dim', 'Added strings use standard tuning: every note keeps its pitch and moves to the frets that play it there.'));
            } else if (restandardised && (preview.arrangements || []).some((a) => a.strings_to > a.strings_from
                    && /^Drop /.test(a.from) && !/^Drop /.test(a.to))) {
                detail.appendChild(el('p', 'plugin-retune-dim', 'Adding a string returns a dropped low string to standard — the new string covers its notes.'));
            }
            if (t.large_shift) detail.appendChild(el('p', 'plugin-retune-warn', 'Shifts beyond 3 semitones start to sound processed.'));
            if (t.shift && !options.rubberband) {
                detail.appendChild(el('p', 'plugin-retune-warn', 'This ffmpeg has no rubberband filter — using a lower-quality resample shift.'));
            }
        };
        const notes = [];
        if (!options.ffmpeg) notes.push(el('p', 'plugin-retune-warn', 'ffmpeg was not found, so only conversions that keep the audio unchanged are available.'));
        notes.push(el('p', 'plugin-retune-dim', 'A new song is added next to the original; the original is not changed.'));

        const actions = buttons(
            ['Cancel', 'plugin-retune-btn-ghost', closeModal],
            ['Convert', 'plugin-retune-btn-primary', () => {
                if (current) convert(body, song, current);
            }],
        );
        const convertButton = actions.querySelector('.plugin-retune-btn-primary');
        select.addEventListener('change', describe);
        for (const { pick } of stringSelects) pick.addEventListener('change', describe);
        describe();

        body.replaceChildren(currentTuning, select, stringsBox, detail, ...notes, actions);
        select.focus();
    }

    function convert(body, song, { target, counts, preview }) {
        hooks.busy = true;
        const bar = el('div', 'plugin-retune-bar');
        const fill = el('div', 'plugin-retune-fill');
        bar.appendChild(fill);
        const stage = el('p', 'plugin-retune-dim', 'Starting…');
        body.replaceChildren(el('p', '', `Converting to ${preview.label}…`), bar, stage);

        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const qs = new URLSearchParams({
            filename: song.filename, shift: target.shift, low_adjust: target.low_adjust, strings: JSON.stringify(counts),
        });
        const ws = new WebSocket(`${proto}//${location.host}/ws/plugins/${PLUGIN_ID}/run?${qs}`);
        let finished = false;
        ws.onmessage = (ev) => {
            const msg = JSON.parse(ev.data);
            if (typeof msg.progress === 'number') fill.style.width = `${msg.progress}%`;
            if (msg.stage) stage.textContent = msg.stage;
            if (msg.error) {
                finished = true;
                hooks.busy = false;
                showError(body, msg.error);
            } else if (msg.done) {
                finished = true;
                hooks.busy = false;
                showDone(body, msg);
            }
        };
        ws.onclose = () => {
            if (!finished) {
                hooks.busy = false;
                showError(body, 'Connection to the server was lost.');
            }
        };
    }

    function showDone(body, msg) {
        try { window.feedBack?.emit('library:changed', { reason: 'retune', filename: msg.filename }); } catch (_) { /* */ }
        const report = msg.report || {};
        const label = report.label || report.to || 'Converted';
        const heading = !report.from || report.from === report.to ? label : `${report.from} → ${label}`;
        const lines = [el('p', 'plugin-retune-done', heading), el('p', 'plugin-retune-dim', msg.filename)];
        lines.push(...changeLines(report, ''));
        if (msg.audio_method === 'resample') lines.push(el('p', 'plugin-retune-warn', 'Audio was shifted with the lower-quality resample method.'));
        body.replaceChildren(...lines, buttons(['Close', 'plugin-retune-btn-primary', closeModal]));
    }

    function register() {
        const reg = window.feedBack?.libraryCardActions;
        if (!reg || hooks.registered) return !!hooks.registered;
        reg.register({
            id: ACTION_ID,
            pluginId: PLUGIN_ID,
            label: 'Retune…',
            placement: 'menu',
            order: 21,
            applies: (song) => !!(song && song.filename && song.format === 'sloppak'),
            run: (song) => run(song),
        });
        hooks.registered = true;
        return true;
    }

    if (!register()) {
        let tries = 0;
        const timer = setInterval(() => {
            if (register() || ++tries > 50) clearInterval(timer);
        }, 200);
    }
})();
