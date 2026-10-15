from __future__ import annotations

import contextvars
import copy
import math
import re
from collections import Counter

MAX_FRET = 24
MAX_SHIFT = 7
LARGE_SHIFT = 3
SAME_TIME = 1e-3

STANDARD_OPEN = {
    ("guitar", 4): [40, 45, 50, 55],
    ("guitar", 5): [40, 45, 50, 55, 59],
    ("guitar", 6): [40, 45, 50, 55, 59, 64],
    ("guitar", 7): [35, 40, 45, 50, 55, 59, 64],
    ("guitar", 8): [30, 35, 40, 45, 50, 55, 59, 64],
    ("bass", 4): [28, 33, 38, 43],
    ("bass", 5): [23, 28, 33, 38, 43],
    ("bass", 6): [23, 28, 33, 38, 43, 48],
}

STRING_COUNTS = {"bass": (4, 5), "guitar": (6, 7, 8)}
DEFAULT_STRINGS = {"bass": 4, "guitar": 6}

PITCH_CLASS_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
PITCH_CLASS_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
PITCH_CLASS_DEFAULT = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
NOTE_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


class RetuneError(ValueError):
    pass


def tuning_family(offsets: list[int]) -> str:
    if len(offsets) < 2:
        return "other"
    if all(o == offsets[0] for o in offsets):
        return "standard"
    if offsets[0] == offsets[1] - 2 and all(o == offsets[1] for o in offsets[1:]):
        return "drop"
    return "other"


def tuning_name(offsets: list[int], standard_open: list[int] | None = None) -> str:
    family = tuning_family(offsets)
    if family == "standard":
        return f"{PITCH_CLASS_DEFAULT[(4 + offsets[0]) % 12]} Standard"
    if family == "drop":
        low_open = (standard_open or STANDARD_OPEN[("guitar", 6)])[0]
        return f"Drop {PITCH_CLASS_DEFAULT[(low_open + offsets[0]) % 12]}"
    return "Custom (" + " ".join(f"{o:+d}" if o else "0" for o in offsets) + ")"


def instrument_kind(entry: dict, arrangement: dict | None = None) -> str:
    kind = str(entry.get("type") or "").strip().lower()
    if kind in ("bass", "drums"):
        return kind
    if kind in ("piano", "keys"):
        return "keys"
    name = " ".join(str(v) for v in (entry.get("name"), entry.get("id"), (arrangement or {}).get("name")) if v).lower()
    if "bass" in name:
        return "bass"
    if "drum" in name or "percussion" in name:
        return "drums"
    if "vocal" in name:
        return "vocals"
    if re.search(r"\b(?:keys|piano|keyboard|synth)\b", name):
        return "keys"
    return "guitar"


def is_bass(entry: dict, arrangement: dict | None = None) -> bool:
    return instrument_kind(entry, arrangement) == "bass"


def fretted_kind(entry: dict, arrangement: dict | None = None) -> str:
    return "bass" if is_bass(entry, arrangement) else "guitar"


def is_pitched_chart(entry: dict, arrangement: dict | None = None) -> bool:
    return (bool(entry.get("file")) and not entry.get("drum_tab")
            and instrument_kind(entry, arrangement) in ("guitar", "bass"))


def _iter_chart_notes(arrangement: dict):
    for n in arrangement.get("notes") or []:
        yield n
    for c in arrangement.get("chords") or []:
        for n in c.get("notes") or []:
            yield n
    for phrase in arrangement.get("phrases") or []:
        for level in phrase.get("levels") or []:
            for n in level.get("notes") or []:
                yield n
            for c in level.get("chords") or []:
                for n in c.get("notes") or []:
                    yield n


def string_count(entry: dict, arrangement: dict, tuning: list[int]) -> int:
    highest = max((int(n.get("s", 0)) for n in _iter_chart_notes(arrangement)), default=-1)
    for t in arrangement.get("templates") or []:
        frets = t.get("frets") or []
        for s, f in enumerate(frets):
            if f is not None and f >= 0:
                highest = max(highest, s)
    count = len(tuning) if tuning else 6
    if is_bass(entry, arrangement) and count == 6:
        count = 4
    return max(count, highest + 1)


def standard_open(entry: dict, arrangement: dict, count: int) -> list[int]:
    kind = fretted_kind(entry, arrangement)
    key = (kind, count)
    if key in STANDARD_OPEN:
        return STANDARD_OPEN[key]
    base = STANDARD_OPEN[(kind, 6)]
    if count < len(base):
        return base[:count]
    return base + [base[-1] + 5 * (i + 1) for i in range(count - len(base))]


def source_tuning(entry: dict, arrangement: dict | None) -> list[int]:
    tuning = entry.get("tuning")
    if tuning is None and arrangement is not None:
        tuning = arrangement.get("tuning")
    if tuning is None:
        tuning = [0, 0, 0, 0, 0, 0]
    return [int(o) for o in tuning]


def reference_entry(manifest: dict, arrangements: dict[str, dict]) -> dict | None:
    charts = [e for e in manifest.get("arrangements") or []
              if is_pitched_chart(e, arrangements.get(e.get("file")))]
    for e in charts:
        if not is_bass(e, arrangements.get(e["file"])):
            return e
    return charts[0] if charts else None


def reference_tuning(ref: dict, files: dict[str, dict]) -> tuple[list[int], list[int]]:
    arrangement = files.get(ref["file"]) or {}
    src = source_tuning(ref, arrangement)
    return src, standard_open(ref, arrangement, string_count(ref, arrangement, src))


def low_adjust_for(src: list[int], std: list[int], ref_src: list[int], ref_std: list[int],
                   low_adjust: int) -> int:
    if not low_adjust or len(src) < 2 or len(ref_src) < 2:
        return 0
    same_gap = src[0] - src[1] == ref_src[0] - ref_src[1]
    same_note = (std[0] + src[0]) % 12 == (ref_std[0] + ref_src[0]) % 12
    return low_adjust if same_gap and same_note else 0


def target_tuning(src: list[int], shift: int, low_adjust: int) -> list[int]:
    out = [o + shift for o in src]
    if out:
        out[0] += low_adjust
    return out


def list_targets(ref_src: list[int], ref_open: list[int]) -> list[dict]:
    family = tuning_family(ref_src)
    adjusts = [0]
    if family == "standard":
        adjusts.append(-2)
    elif family == "drop":
        adjusts.append(2)
    targets = []
    for adjust in adjusts:
        for shift in range(-MAX_SHIFT, MAX_SHIFT + 1):
            if shift == 0 and adjust == 0:
                continue
            offsets = target_tuning(ref_src, shift, adjust)
            targets.append({
                "shift": shift,
                "low_adjust": adjust,
                "offsets": offsets,
                "name": tuning_name(offsets, ref_open),
                "family": tuning_family(offsets),
                "large_shift": abs(shift) > LARGE_SHIFT,
            })
    targets.sort(key=lambda t: (t["family"] != "standard", -t["offsets"][-1], t["low_adjust"]))
    keep = {
        "shift": 0,
        "low_adjust": 0,
        "offsets": list(ref_src),
        "name": tuning_name(ref_src, ref_open),
        "family": "keep",
        "large_shift": False,
        "keep": True,
    }
    return [keep, *targets]


def _same_time(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) < SAME_TIME


_highest_fret: contextvars.ContextVar[int] = contextvars.ContextVar("highest_fret", default=MAX_FRET)


def _valid_fret(f: int) -> bool:
    return 0 <= f <= _highest_fret.get()


def _candidates(pitch: int, string: int, opens: list[int], occupied: set[int]):
    options = []
    for octave_rank, p in enumerate((pitch, pitch + 12, pitch - 12)):
        for s, open_pitch in enumerate(opens):
            if s in occupied:
                continue
            f = p - open_pitch
            if _valid_fret(f):
                options.append((octave_rank, s != string, abs(s - string), f, s))
    options.sort()
    return [(s, f, rank) for rank, _, _, f, s in options]


class ChartReport:
    def __init__(self):
        self.refretted = 0
        self.relocated = 0
        self.octave_moved = 0
        self.removed = 0
        self.slides_cleared = 0
        self.harmonics_moved = 0

    def add(self, other: "ChartReport"):
        for k, v in vars(other).items():
            setattr(self, k, getattr(self, k) + v)

    def as_dict(self) -> dict:
        return dict(vars(self))


class StringPlan:
    def __init__(self, target_of: list[int | None], src_opens: list[int], opens: list[int], offset: int = 0):
        self.target_of = target_of
        self.src_opens = src_opens
        self.opens = opens
        self.offset = offset

    @property
    def source_count(self) -> int:
        return len(self.target_of)

    @property
    def target_count(self) -> int:
        return len(self.opens)

    def is_identity(self) -> bool:
        return self.source_count == self.target_count and all(
            t == s and self.src_opens[s] == self.opens[t] for s, t in enumerate(self.target_of))

    def mapped(self, s: int, f: int) -> tuple[int | None, int]:
        t = self.target_of[s]
        if t is None:
            return None, f
        return t, f + self.src_opens[s] - self.opens[t]

    def nearest_target(self, s: int) -> int:
        return max(0, min(self.target_count - 1, s + self.offset))


def _move_note(note: dict, new_s: int, new_f: int, report: ChartReport):
    old_f = int(note.get("f", 0))
    note["s"] = new_s
    note["f"] = new_f
    for key in ("sl", "slu"):
        target = note.get(key, -1)
        if target is None or target < 0:
            continue
        moved = target + (new_f - old_f)
        if _valid_fret(moved):
            note[key] = moved
        else:
            note[key] = -1
            report.slides_cleared += 1
    if note.get("fg", -1) not in (-1, None):
        note["fg"] = -1


def _place_group(notes: list[dict], plan: StringPlan, report: ChartReport, moved: list,
                 t: float) -> tuple[list[dict], list[tuple[int, int, int]]]:
    pending = []
    original: dict[int, int] = {}
    for note in notes:
        s, f = int(note.get("s", 0)), int(note.get("f", 0))
        original[id(note)] = s
        if not 0 <= s < plan.source_count:
            continue
        target, new_f = plan.mapped(s, f)
        if target is not None and new_f == f:
            note["s"] = target
            continue
        report.refretted += 1
        if note.get("hm"):
            report.harmonics_moved += 1
        if target is not None and _valid_fret(new_f):
            _move_note(note, target, new_f, report)
            moved.append((t, new_f))
            continue
        preferred = target if target is not None else plan.nearest_target(s)
        pending.append((note, plan.src_opens[s] + f, preferred))

    unplaced = {id(note) for note, _, _ in pending}
    occupied = {int(n.get("s", 0)) for n in notes if id(n) not in unplaced}
    removed = set()
    for note, pitch, preferred in pending:
        for cand_s, cand_f, octave_rank in _candidates(pitch, preferred, plan.opens, occupied):
            _move_note(note, cand_s, cand_f, report)
            moved.append((t, cand_f))
            occupied.add(cand_s)
            if octave_rank:
                report.octave_moved += 1
            else:
                report.relocated += 1
            break
        else:
            report.removed += 1
            removed.add(id(note))

    kept = [n for n in notes if id(n) not in removed]
    moves = [(original[id(n)], -1 if id(n) in removed else int(n["s"]), -1 if id(n) in removed else int(n["f"]))
             for n in notes]
    return kept, moves


def _fit_anchors(anchors: list[dict], moved: list[tuple[float, int]]):
    if not moved:
        return
    ordered = sorted(anchors, key=lambda a: float(a.get("time", 0)))
    for i, anchor in enumerate(ordered):
        start = float(anchor.get("time", 0)) - SAME_TIME
        end = float(ordered[i + 1].get("time", 0)) - SAME_TIME if i + 1 < len(ordered) else math.inf
        frets = [f for t, f in moved if start <= t < end and f > 0]
        if not frets:
            continue
        fret = int(anchor.get("fret") or 1)
        width = anchor.get("width") or 4
        lo = min(fret, *frets)
        hi = max(fret + width - 1, *frets)
        anchor["fret"] = lo
        anchor["width"] = hi - lo + 1


def _time_groups(notes: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    for note in sorted(notes, key=lambda n: float(n.get("t", 0))):
        t = float(note.get("t", 0))
        if groups and _same_time(t, groups[-1][-1].get("t", 0)) \
                and t - float(groups[-1][0].get("t", 0)) < 2 * SAME_TIME:
            groups[-1].append(note)
        else:
            groups.append([note])
    return groups


def _refret_notes(notes: list[dict], plan: StringPlan, report, moved) -> list[dict]:
    removed = set()
    for group in _time_groups(notes):
        kept, _ = _place_group(group, plan, report, moved, float(group[0].get("t", 0)))
        kept_ids = {id(n) for n in kept}
        removed.update(id(n) for n in group if id(n) not in kept_ids)
    return [n for n in notes if id(n) not in removed]


def _refret_chord(chord: dict, plan: StringPlan, report, moved) -> list[tuple[int, int, int]]:
    kept, moves = _place_group(chord.get("notes") or [], plan, report, moved, float(chord.get("t", 0)))
    chord["notes"] = kept
    return moves


def _map_template(template: dict, plan: StringPlan) -> tuple[dict, dict[int, int]]:
    out = copy.deepcopy(template)
    frets = list(out.get("frets") or [])
    fingers = list(out.get("fingers") or [-1] * len(frets))
    fingers += [-1] * (len(frets) - len(fingers))
    width = len(frets) if plan.target_count == plan.source_count else plan.target_count
    new_frets = [-1] * width
    new_fingers = [-1] * width
    for s, f in enumerate(frets):
        if f is not None and f >= 0 and plan.source_count <= s < width:
            new_frets[s], new_fingers[s] = f, fingers[s]
    shape = [{"s": s, "f": f} for s, f in enumerate(frets)
             if f is not None and f >= 0 and s < plan.source_count]
    _, moves = _place_group(shape, plan, ChartReport(), [], 0.0)
    placed: dict[int, int] = {}
    for orig_s, new_s, new_f in moves:
        placed[orig_s] = new_s
        if new_s < 0:
            continue
        new_frets += [-1] * (new_s + 1 - len(new_frets))
        new_fingers += [-1] * (new_s + 1 - len(new_fingers))
        new_frets[new_s] = new_f
        unchanged = plan.mapped(orig_s, frets[orig_s]) == (new_s, new_f) and new_f == frets[orig_s]
        new_fingers[new_s] = fingers[orig_s] if unchanged else (0 if new_f == 0 else -1)
    out["frets"] = new_frets
    if "fingers" in template:
        out["fingers"] = new_fingers
    return out, placed


class _TemplateBook:
    def __init__(self, templates: list[dict], plan: StringPlan):
        self.originals = templates
        mapped = [_map_template(t, plan) for t in templates]
        self.templates = [template for template, _ in mapped]
        self.placed = [placed for _, placed in mapped]
        self.variants: dict[tuple, int] = {}

    def resolve(self, old_id: int, moves: list[tuple[int, int, int]]) -> int:
        if not (0 <= old_id < len(self.placed)):
            return old_id
        base = self.templates[old_id]
        placed = self.placed[old_id]
        frets = list(base.get("frets") or [])
        for orig_s, new_s, _ in moves:
            previous = placed.get(orig_s, -1)
            if 0 <= previous < len(frets) and previous != new_s:
                frets[previous] = -1
        for _, new_s, new_f in moves:
            if new_s >= 0:
                frets += [-1] * (new_s + 1 - len(frets))
                frets[new_s] = new_f
        if frets == list(base.get("frets") or []):
            return old_id
        key = (old_id, tuple(frets))
        if key in self.variants:
            return self.variants[key]
        variant = copy.deepcopy(base)
        if "fingers" in variant:
            fingers = list(variant["fingers"]) + [-1] * (len(frets) - len(variant["fingers"]))
            base_frets = list(base.get("frets") or [])
            variant["fingers"] = [
                fingers[s] if s < len(base_frets) and base_frets[s] == f else (0 if f == 0 else -1)
                for s, f in enumerate(frets)
            ]
        variant["frets"] = frets
        self.templates.append(variant)
        self.variants[key] = len(self.templates) - 1
        return self.variants[key]


def _refret_layer(layer: dict, book: _TemplateBook, plan: StringPlan, report):
    moved: list[tuple[float, int]] = []
    if "notes" in layer:
        layer["notes"] = _refret_notes(layer.get("notes") or [], plan, report, moved)
    usage: dict[int, list[tuple[float, int]]] = {}
    for chord in layer.get("chords") or []:
        moves = _refret_chord(chord, plan, report, moved)
        old_id = int(chord.get("id", 0))
        new_id = book.resolve(old_id, moves)
        chord["id"] = new_id
        usage.setdefault(old_id, []).append((float(chord.get("t", 0)), new_id))
    for hs in layer.get("handshapes") or []:
        old_id = int(hs.get("chord_id", 0))
        start, end = float(hs.get("start_time", 0)), float(hs.get("end_time", 0))
        ids = Counter(new_id for t, new_id in usage.get(old_id, [])
                      if start - SAME_TIME <= t <= end + SAME_TIME)
        if ids:
            hs["chord_id"] = ids.most_common(1)[0][0]
    _fit_anchors(layer.get("anchors") or [], moved)


def refret_arrangement(arrangement: dict, plan: StringPlan, capo: int = 0) -> ChartReport:
    report = ChartReport()
    if plan.is_identity():
        return report
    token = _highest_fret.set(MAX_FRET - max(0, int(capo or 0)))
    try:
        return _refret_arrangement(arrangement, plan, report)
    finally:
        _highest_fret.reset(token)


def _refret_arrangement(arrangement: dict, plan: StringPlan, report: ChartReport) -> ChartReport:
    book = _TemplateBook(arrangement.get("templates") or [], plan)
    _refret_layer(arrangement, book, plan, report)
    counts_top_level = bool(arrangement.get("notes") or arrangement.get("chords"))
    for phrase in arrangement.get("phrases") or []:
        levels = phrase.get("levels") or []
        hardest = max(levels, key=lambda lv: lv.get("difficulty", 0), default=None)
        for level in levels:
            counted = not counts_top_level and level is hardest
            _refret_layer(level, book, plan, report if counted else ChartReport())
    if "templates" in arrangement:
        arrangement["templates"] = book.templates
    return report


def transpose_note_name(name: str, shift: int) -> str:
    if not isinstance(name, str) or not name or name[0].upper() not in NOTE_BASE:
        return name
    root = name[0].upper()
    pc = NOTE_BASE[root]
    i = 1
    accidental = ""
    while i < len(name) and name[i] in "#b♯♭":
        accidental += name[i]
        pc += 1 if name[i] in "#♯" else -1
        i += 1
    rest = name[i:]
    new_pc = (pc + shift) % 12
    if any(a in "b♭" for a in accidental):
        table = PITCH_CLASS_FLAT
    elif accidental:
        table = PITCH_CLASS_SHARP
    else:
        table = PITCH_CLASS_DEFAULT
    return table[new_pc] + rest


def transpose_key_signature(ks: int, shift: int) -> int:
    pc = (int(ks) * 7 + shift) % 12
    fifths = (pc * 7) % 12
    if fifths > 6 or (fifths == 6 and ks < 0):
        fifths -= 12
    return fifths


def transpose_notation(doc: dict, shift: int):
    measures = doc.get("measures") or []
    if measures and measures[0].get("ks") is None:
        measures[0]["ks"] = 0
    for measure in measures:
        if "ks" in measure and measure["ks"] is not None:
            measure["ks"] = transpose_key_signature(measure["ks"], shift)
        for staff in (measure.get("staves") or {}).values():
            for voice in (staff or {}).get("voices") or []:
                for beat in voice.get("beats") or []:
                    for note in beat.get("notes") or []:
                        if isinstance(note.get("midi"), (int, float)):
                            note["midi"] = max(0, min(127, int(note["midi"]) + shift))
                            note.pop("acc", None)


def transpose_keys_chart(arrangement: dict, shift: int):
    for note in _iter_chart_notes(arrangement):
        try:
            midi = int(note.get("s", 0)) * 24 + int(note.get("f", 0))
        except (TypeError, ValueError):
            continue
        midi = max(0, min(127, midi + shift))
        note["s"], note["f"] = divmod(midi, 24)


def transpose_vocal_pitch(doc: dict, shift: int):
    for note in doc.get("notes") or []:
        if isinstance(note.get("midi"), (int, float)):
            note["midi"] = max(0, min(127, note["midi"] + shift))


def transpose_contour(doc: dict, shift: int):
    ratio = 2 ** (shift / 12)
    for sample in doc.get("samples") or []:
        hz = sample.get("hz")
        if isinstance(hz, (int, float)) and hz > 0:
            sample["hz"] = round(hz * ratio, 2)


def transpose_keys(doc: dict, shift: int):
    for event in doc.get("events") or []:
        if "key" in event:
            event["key"] = transpose_note_name(event["key"], shift)


def transpose_harmony(doc: dict, shift: int):
    for event in doc.get("events") or []:
        for field in ("root", "bass"):
            if event.get(field):
                event[field] = transpose_note_name(event[field], shift)


SIDE_FILE_TRANSFORMS = {
    "vocal_pitch": transpose_vocal_pitch,
    "vocal_pitch_contour": transpose_contour,
    "keys": transpose_keys,
    "harmony": transpose_harmony,
}


def chart_string_count(entry: dict, arrangement: dict | None) -> int:
    return string_count(entry, arrangement or {}, source_tuning(entry, arrangement))


def string_choices(entry: dict, arrangement: dict, count: int | None = None) -> list[int]:
    if count is None:
        count = chart_string_count(entry, arrangement)
    choices = STRING_COUNTS[fretted_kind(entry, arrangement)]
    return list(choices) if count in choices else [count]


def string_alignment(std_src: list[int], std_tgt: list[int]) -> int:
    best = None
    for k in range(-(len(std_src) - 1), len(std_tgt)):
        overlap = [s for s in range(len(std_src)) if 0 <= s + k < len(std_tgt)]
        if overlap and all(std_src[s] == std_tgt[s + k] for s in overlap):
            if best is None or len(overlap) > best[1]:
                best = (k, len(overlap))
    if best is None:
        raise RetuneError("The two string layouts share no strings")
    return best[0]


def extended_tuning(src: list[int], shift: int, offset: int, target_count: int, drop_lowest: bool) -> list[int]:
    base = [o + shift for o in src]
    family = tuning_family(src)
    level = base[1] if family in ("standard", "drop") and len(base) >= 2 else base[0]
    if family == "drop":
        base[0] = level
    out = []
    for t in range(target_count):
        s = t - offset
        if s < 0:
            out.append(level)
        elif s < len(base):
            out.append(base[s])
        else:
            out.append(base[-1])
    if drop_lowest:
        out[0] -= 2
    return out


def plan_arrangement(entry: dict, arrangement: dict, ref_src: list[int], ref_std: list[int],
                     shift: int, low_adjust: int, strings: int | None = None, count: int | None = None):
    src = source_tuning(entry, arrangement)
    if count is None:
        count = string_count(entry, arrangement, src)
    src = src or [0] * count
    std = standard_open(entry, arrangement, count)
    adjust = low_adjust_for(src, std, ref_src, ref_std, low_adjust)
    tgt = target_tuning(src, shift, adjust)

    def padded(offsets):
        return (offsets + [offsets[-1]] * count)[:count]

    src_opens = [std[s] + padded(src)[s] + shift for s in range(count)]
    target_count = count if strings is None else strings
    if target_count == count:
        opens = [std[s] + padded(tgt)[s] for s in range(count)]
        return StringPlan(list(range(count)), src_opens, opens), src, tgt, std, std

    if target_count not in string_choices(entry, arrangement, count):
        name = entry.get("name") or entry.get("id")
        raise RetuneError(f"{name} can't be converted from {count} to {target_count} strings")
    target_std = STANDARD_OPEN[(fretted_kind(entry, arrangement), target_count)]
    offset = string_alignment(std, target_std)
    keeps_tuning = shift == 0 and low_adjust == 0
    drop_target = tuning_family(padded(tgt)) == "drop" and not keeps_tuning
    tgt = extended_tuning(padded(src), shift, offset, target_count, drop_lowest=drop_target)
    target_of = [s + offset if 0 <= s + offset < target_count else None for s in range(count)]
    opens = [target_std[t] + tgt[t] for t in range(target_count)]
    return StringPlan(target_of, src_opens, opens, offset), src, tgt, std, target_std


def tuning_label(offsets: list[int], std: list[int], kind: str) -> str:
    name = tuning_name(offsets, std)
    return name if len(std) == DEFAULT_STRINGS[kind] else f"{name} ({len(std)}-string)"


def retune_pack(manifest: dict, files: dict[str, dict], shift: int, low_adjust: int,
                strings: dict[str, int] | None = None, side_files: bool = True) -> dict:
    strings = dict(strings or {})
    if abs(shift) > MAX_SHIFT:
        raise RetuneError(f"Shift is limited to ±{MAX_SHIFT} semitones")
    if low_adjust not in (-2, 0, 2):
        raise RetuneError("Low-string adjustment must be -2, 0 or +2")
    ref = reference_entry(manifest, files)
    if ref is None:
        raise RetuneError("The pack has no fretted arrangement to retune")
    ref_src, ref_std = reference_tuning(ref, files)

    fretted = []
    for entry in manifest.get("arrangements") or []:
        if not is_pitched_chart(entry, files.get(entry.get("file"))):
            continue
        arrangement = files.get(entry["file"])
        if arrangement is None:
            raise RetuneError(f"Arrangement file {entry['file']} is missing")
        fretted.append((entry, arrangement, chart_string_count(entry, arrangement)))

    by_id = {entry["id"]: (entry, count) for entry, _, count in fretted if entry.get("id")}
    for arr_id, wanted in strings.items():
        if arr_id not in by_id:
            raise RetuneError(f"Unknown fretted arrangement {arr_id!r}")
        if not isinstance(wanted, int) or isinstance(wanted, bool):
            raise RetuneError(f"String count for {arr_id!r} must be a number")
    by_file: dict[str, tuple[str, int]] = {}
    for entry, _, count in fretted:
        name = entry.get("id") or entry.get("name")
        wanted = strings.get(entry.get("id"), count)
        other = by_file.setdefault(entry["file"], (name, wanted))
        if other[1] != wanted:
            raise RetuneError(f"{other[0]!r} and {name!r} share a chart file, so they need the same string count")
    changes_strings = any(wanted != by_id[arr_id][1] for arr_id, wanted in strings.items())
    if shift == 0 and low_adjust == 0 and not changes_strings:
        raise RetuneError("Target tuning is the same as the source")

    plans = [(entry, arrangement, plan_arrangement(entry, arrangement, ref_src, ref_std, shift, low_adjust,
                                                   strings.get(entry.get("id")), count))
             for entry, arrangement, count in fretted]

    total = ChartReport()
    arrangements = []
    done: set[str] = set()

    def first_time(path) -> bool:
        if path in done:
            return False
        done.add(path)
        return True

    for entry in (manifest.get("arrangements") or []) if side_files and shift else []:
        notation = entry.get("notation")
        if notation and notation in files and first_time(notation):
            transpose_notation(files[notation], shift)
        chart = files.get(entry.get("file"))
        if chart is not None and not entry.get("drum_tab") \
                and instrument_kind(entry, chart) == "keys" and first_time(entry["file"]):
            transpose_keys_chart(chart, shift)

    reports_by_file: dict[str, ChartReport] = {}
    for entry, arrangement, (plan, src, tgt, std, target_std) in plans:
        if first_time(entry["file"]):
            capo = entry.get("capo", arrangement.get("capo", 0))
            report = reports_by_file[entry["file"]] = refret_arrangement(arrangement, plan, capo)
            total.add(report)
        else:
            report = reports_by_file.get(entry["file"], ChartReport())
        entry["tuning"] = tgt
        if "tuning" in arrangement:
            arrangement["tuning"] = list(tgt)
        kind = fretted_kind(entry, arrangement)
        arrangements.append({
            "id": entry.get("id"),
            "name": entry.get("name") or entry.get("id"),
            "kind": kind,
            "from": tuning_label(src, std, kind),
            "to": tuning_label(tgt, target_std, kind),
            "tuning": tgt,
            "strings_from": len(std),
            "strings_to": len(target_std),
            **report.as_dict(),
        })

    if side_files and shift:
        for key, transform in SIDE_FILE_TRANSFORMS.items():
            path = manifest.get(key)
            if isinstance(path, str) and path in files and first_time(path):
                transform(files[path], shift)

    ref_result = next((a for (entry, *_), a in zip(plans, arrangements) if entry is ref), None)
    to_name = ref_result["to"] if ref_result else tuning_name(target_tuning(ref_src, shift, low_adjust), ref_std)
    covered = set()
    if ref_result and ref_result["strings_to"] != ref_result["strings_from"]:
        covered.add((ref_result["strings_to"], ref_result["kind"]))
    extended = sorted({f"{a['strings_to']}-string {a['kind']}" for a in arrangements
                       if a["strings_to"] != a["strings_from"] and (a["strings_to"], a["kind"]) not in covered})
    return {
        "shift": shift,
        "low_adjust": low_adjust,
        "from": tuning_name(ref_src, ref_std),
        "to": to_name,
        "label": " ".join([to_name, *extended]),
        "arrangements": arrangements,
        "chart": total.as_dict(),
    }


def pitch_ratio(shift: int) -> float:
    return math.pow(2, shift / 12)
