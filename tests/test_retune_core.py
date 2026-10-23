import copy

import pytest


def lead(tuning, notes=None, chords=None, templates=None, handshapes=None, **extra):
    return {
        "name": "Lead",
        "tuning": tuning,
        "capo": 0,
        "notes": notes or [],
        "chords": chords or [],
        "anchors": [{"time": 0.0, "fret": 1, "width": 4}],
        "handshapes": handshapes or [],
        "templates": templates or [],
        **extra,
    }


def manifest_for(lead_tuning, bass_tuning=None, **extra):
    arrangements = [{"id": "lead", "name": "Lead", "file": "arrangements/lead.json", "tuning": lead_tuning}]
    if bass_tuning is not None:
        arrangements.append({"id": "bass", "name": "Bass", "file": "arrangements/bass.json", "tuning": bass_tuning})
    arrangements.append({"id": "drums", "name": "Drums", "type": "drums", "drum_tab": "drum_tab.json"})
    return {
        "title": "Song", "artist": "Band", "duration": 10.0,
        "arrangements": arrangements,
        "stems": [{"id": "full", "file": "stems/full.ogg", "default": True}],
        **extra,
    }


@pytest.mark.parametrize("offsets,name", [
    ([0] * 6, "E Standard"),
    ([-1] * 6, "Eb Standard"),
    ([-4] * 6, "C Standard"),
    ([-2, 0, 0, 0, 0, 0], "Drop D"),
    ([-3, -1, -1, -1, -1, -1], "Drop C#"),
    ([-1] * 4, "Eb Standard"),
    ([0, 0, 0, -1, 0, 0], "Custom (0 0 0 -1 0 0)"),
])
def test_tuning_name(core, offsets, name):
    assert core.tuning_name(offsets) == name


def test_seven_string_drop_is_named_after_its_low_string(core):
    assert core.tuning_name([-2, 0, 0, 0, 0, 0, 0], core.STANDARD_OPEN[("guitar", 7)]) == "Drop A"


def test_targets_from_eb_standard_cover_standard_and_drop(core):
    keep, *rest = core.list_targets([-1] * 6, core.STANDARD_OPEN[("guitar", 6)])
    targets = {t["name"]: t for t in rest}
    assert keep["keep"] and keep["name"] == "Eb Standard" and (keep["shift"], keep["low_adjust"]) == (0, 0)
    assert (targets["E Standard"]["shift"], targets["E Standard"]["low_adjust"]) == (1, 0)
    assert (targets["Drop D"]["shift"], targets["Drop D"]["low_adjust"]) == (1, -2)
    assert (targets["Drop C#"]["shift"], targets["Drop C#"]["low_adjust"]) == (0, -2)
    assert "Eb Standard" not in targets
    assert targets["B Standard"]["large_shift"]


def test_targets_from_drop_offer_drop_and_standard(core):
    targets = {t["name"]: t for t in core.list_targets([-2, 0, 0, 0, 0, 0], core.STANDARD_OPEN[("guitar", 6)])}
    assert (targets["Drop C"]["shift"], targets["Drop C"]["low_adjust"]) == (-2, 0)
    assert (targets["E Standard"]["shift"], targets["E Standard"]["low_adjust"]) == (0, 2)


def test_standard_to_standard_keeps_frets_and_shifts_side_files(core):
    notes = [{"t": 1.0, "s": 0, "f": 0}, {"t": 2.0, "s": 5, "f": 12, "sl": 14}]
    files = {
        "arrangements/lead.json": lead([-1] * 6, notes=notes),
        "arrangements/bass.json": lead([-1] * 6, notes=[{"t": 1.0, "s": 0, "f": 3}], name="Bass"),
        "vocal_pitch.json": {"version": 1, "notes": [{"t": 1.0, "d": 0.5, "midi": 63}]},
        "vocal_pitch_contour.json": {"version": 1, "samples": [{"t": 0.0, "hz": 220.0}]},
        "keys.json": {"version": 1, "events": [{"t": 0.0, "key": "Ebm", "scale": "natural_minor"}]},
        "harmony.json": {"version": 1, "events": [{"t": 0.0, "root": "Bb", "quality": "7", "bass": "D"}]},
    }
    manifest = manifest_for([-1] * 6, [-1] * 6, vocal_pitch="vocal_pitch.json",
                            vocal_pitch_contour="vocal_pitch_contour.json",
                            keys="keys.json", harmony="harmony.json")
    before = copy.deepcopy(files["arrangements/lead.json"]["notes"])

    report = core.retune_pack(manifest, files, 1, 0)

    assert report["from"] == "Eb Standard" and report["to"] == "E Standard"
    assert manifest["arrangements"][0]["tuning"] == [0] * 6
    assert manifest["arrangements"][1]["tuning"] == [0] * 6
    assert files["arrangements/lead.json"]["tuning"] == [0] * 6
    assert files["arrangements/lead.json"]["notes"] == before
    assert files["vocal_pitch.json"]["notes"][0]["midi"] == 64
    assert files["vocal_pitch_contour.json"]["samples"][0]["hz"] == pytest.approx(233.08, abs=0.01)
    assert files["keys.json"]["events"][0]["key"] == "Em"
    assert files["harmony.json"]["events"][0]["root"] == "B"
    assert files["harmony.json"]["events"][0]["bass"] == "Eb"
    assert report["chart"]["refretted"] == 0
    assert "tuning" not in manifest["arrangements"][2]


def test_drop_d_to_e_standard_refrets_low_string(core):
    templates = [{"name": "D5", "fingers": [0, 1, 1, -1, -1, -1], "frets": [0, 0, 0, -1, -1, -1]},
                 {"name": "G5", "fingers": [1, 1, 1, -1, -1, -1], "frets": [5, 5, 5, -1, -1, -1]}]
    chords = [
        {"t": 1.0, "id": 0, "notes": [{"s": 0, "f": 0}, {"s": 1, "f": 0}, {"s": 2, "f": 0}]},
        {"t": 2.0, "id": 1, "notes": [{"s": 0, "f": 5}, {"s": 1, "f": 5}, {"s": 2, "f": 5}]},
    ]
    notes = [
        {"t": 3.0, "s": 0, "f": 0, "fg": 0},
        {"t": 3.5, "s": 0, "f": 7, "sl": 9, "fg": 1},
        {"t": 4.0, "s": 1, "f": 2},
    ]
    handshapes = [{"chord_id": 0, "start_time": 0.9, "end_time": 1.5}]
    files = {
        "arrangements/lead.json": lead([-2, 0, 0, 0, 0, 0], notes=notes, chords=chords,
                                       templates=templates, handshapes=handshapes),
        "arrangements/bass.json": lead([0, 0, 0, 0], notes=[{"t": 1.0, "s": 0, "f": 0}], name="Bass"),
    }
    manifest = manifest_for([-2, 0, 0, 0, 0, 0], [0, 0, 0, 0])

    report = core.retune_pack(manifest, files, 0, 2)
    arr = files["arrangements/lead.json"]

    assert report["to"] == "E Standard"
    assert manifest["arrangements"][0]["tuning"] == [0] * 6
    assert manifest["arrangements"][1]["tuning"] == [0, 0, 0, 0]
    assert files["arrangements/bass.json"]["notes"] == [{"t": 1.0, "s": 0, "f": 0}]

    open_d, fretted, other = arr["notes"]
    assert (open_d["s"], open_d["f"], open_d["fg"]) == (0, 10, -1)
    assert (fretted["s"], fretted["f"], fretted["sl"], fretted["fg"]) == (0, 5, 7, -1)
    assert (other["s"], other["f"]) == (1, 2)

    power_open, power_g = arr["chords"]
    assert [(n["s"], n["f"]) for n in power_open["notes"]] == [(0, 10), (1, 0), (2, 0)]
    assert [(n["s"], n["f"]) for n in power_g["notes"]] == [(0, 3), (1, 5), (2, 5)]
    assert power_g["id"] == 1
    assert arr["templates"][1]["frets"] == [3, 5, 5, -1, -1, -1]
    assert arr["templates"][1]["fingers"] == [-1, 1, 1, -1, -1, -1]
    assert power_open["id"] == 0
    assert arr["templates"][0]["frets"] == [10, 0, 0, -1, -1, -1]
    assert len(arr["templates"]) == 2
    assert arr["handshapes"][0]["chord_id"] == 0
    assert report["chart"]["octave_moved"] == 2
    assert report["chart"]["refretted"] == 4


def test_e_standard_to_drop_d_moves_high_low_string_notes_up_a_string(core):
    notes = [{"t": 1.0, "s": 0, "f": 23}, {"t": 2.0, "s": 0, "f": 3}]
    files = {"arrangements/lead.json": lead([0] * 6, notes=notes)}
    manifest = manifest_for([0] * 6)

    report = core.retune_pack(manifest, files, 0, -2)

    high, low = files["arrangements/lead.json"]["notes"]
    assert (high["s"], high["f"]) == (1, 18)
    assert (low["s"], low["f"]) == (0, 5)
    assert report["chart"]["relocated"] == 1
    assert manifest["arrangements"][0]["tuning"] == [-2, 0, 0, 0, 0, 0]


def test_relocation_avoids_strings_already_sounding(core):
    notes = [{"t": 1.0, "s": 0, "f": 23}, {"t": 1.0, "s": 1, "f": 0}]
    files = {"arrangements/lead.json": lead([0] * 6, notes=notes)}

    core.retune_pack(manifest_for([0] * 6), files, 0, -2)

    moved = files["arrangements/lead.json"]["notes"][0]
    assert (moved["s"], moved["f"]) == (2, 13)


def test_phrase_levels_are_refretted(core):
    phrases = [{"start_time": 0, "end_time": 5, "max_difficulty": 0,
                "levels": [{"difficulty": 0, "notes": [{"t": 1.0, "s": 0, "f": 5}], "chords": [],
                            "anchors": [], "handshapes": []}]}]
    files = {"arrangements/lead.json": lead([-2, 0, 0, 0, 0, 0], phrases=phrases)}

    core.retune_pack(manifest_for([-2, 0, 0, 0, 0, 0]), files, -2, 0)
    assert files["arrangements/lead.json"]["phrases"][0]["levels"][0]["notes"][0]["f"] == 5

    core.retune_pack(manifest_for([-4, -2, -2, -2, -2, -2]), files, 0, 2)
    assert files["arrangements/lead.json"]["phrases"][0]["levels"][0]["notes"][0]["f"] == 3


def test_notation_is_transposed(core):
    notation = {"version": 1, "instrument": "piano", "staves": [{"id": "rh", "clef": "G2"}],
                "measures": [{"idx": 1, "t": 0.0, "ks": -3, "staves": {"rh": {"voices": [
                    {"v": 1, "beats": [{"t": 0.0, "dur": 4, "notes": [{"midi": 63}]}]}]}}}]}
    manifest = manifest_for([-1] * 6)
    manifest["arrangements"].append({"id": "keys", "type": "piano", "notation": "arrangements/notation_keys.json"})
    files = {"arrangements/lead.json": lead([-1] * 6), "arrangements/notation_keys.json": notation}

    core.retune_pack(manifest, files, 1, 0)

    measure = notation["measures"][0]
    assert measure["ks"] == 4
    assert measure["staves"]["rh"]["voices"][0]["beats"][0]["notes"][0]["midi"] == 64
    assert "tuning" not in manifest["arrangements"][-1]


@pytest.mark.parametrize("ks,shift,expected", [(0, 1, -5), (-3, 1, 4), (0, -1, 5), (-1, 2, 1), (6, 0, 6), (-6, 0, -6)])
def test_key_signature_transposition(core, ks, shift, expected):
    assert core.transpose_key_signature(ks, shift) == expected


@pytest.mark.parametrize("name,shift,expected", [("Em", 1, "Fm"), ("Ebm", 1, "Em"), ("F#", 1, "G"),
                                                  ("Bb", 2, "C"), ("C", 1, "C#"), ("Ab7", -1, "G7")])
def test_note_name_transposition(core, name, shift, expected):
    assert core.transpose_note_name(name, shift) == expected


def test_rejects_identity_and_out_of_range(core):
    files = {"arrangements/lead.json": lead([0] * 6)}
    with pytest.raises(core.RetuneError):
        core.retune_pack(manifest_for([0] * 6), files, 0, 0)
    with pytest.raises(core.RetuneError):
        core.retune_pack(manifest_for([0] * 6), files, 9, 0)
    with pytest.raises(core.RetuneError):
        core.retune_pack(manifest_for([0] * 6), files, 0, 1)


def test_bass_with_padded_six_element_tuning(core):
    entry = {"id": "bass", "name": "Bass", "file": "b.json", "tuning": [-2, 0, 0, 0, 0, 0]}
    arr = lead([-2, 0, 0, 0, 0, 0], notes=[{"t": 1.0, "s": 3, "f": 2}])
    assert core.string_count(entry, arr, entry["tuning"]) == 4


def test_notation_drops_spelling_overrides_and_gains_a_key_signature(core):
    notation = {"version": 1, "instrument": "piano", "staves": [{"id": "rh", "clef": "G2"}],
                "measures": [{"idx": 1, "t": 0.0, "staves": {"rh": {"voices": [
                    {"v": 1, "beats": [{"t": 0.0, "dur": 4, "notes": [{"midi": 61, "acc": 1}]}]}]}}},
                    {"idx": 2, "t": 2.0, "staves": {}}]}

    core.transpose_notation(notation, 1)

    first = notation["measures"][0]
    assert first["ks"] == -5
    assert first["staves"]["rh"]["voices"][0]["beats"][0]["notes"][0] == {"midi": 62}
    assert "ks" not in notation["measures"][1]


def test_anchors_grow_to_cover_moved_notes(core):
    notes = [{"t": 1.0, "s": 0, "f": 0}, {"t": 1.5, "s": 0, "f": 3}, {"t": 5.0, "s": 1, "f": 7}]
    anchors = [{"time": 0.0, "fret": 1, "width": 4}, {"time": 4.0, "fret": 7, "width": 4}]
    files = {"arrangements/lead.json": lead([-2, 0, 0, 0, 0, 0], notes=notes, anchors=anchors)}

    core.retune_pack(manifest_for([-2, 0, 0, 0, 0, 0]), files, 0, 2)

    first, second = files["arrangements/lead.json"]["anchors"]
    assert (first["fret"], first["width"]) == (1, 10)
    assert (second["fret"], second["width"]) == (7, 4)


@pytest.mark.parametrize("entry,kind", [
    ({"type": "piano", "name": "Lead"}, "keys"),
    ({"type": "keys"}, "keys"),
    ({"name": "Keys"}, "keys"),
    ({"name": "Synth Pad"}, "keys"),
    ({"name": "Monkeys Medley"}, "guitar"),
    ({"name": "Lead Vocals"}, "vocals"),
    ({"type": "rhythm", "name": "Bass 2"}, "bass"),
    ({"type": "drums"}, "drums"),
    ({"name": "Lead"}, "guitar"),
])
def test_instrument_kind_matches_the_host(core, entry, kind):
    assert core.instrument_kind(entry) == kind


def test_keys_chart_is_neither_reference_nor_refretted(core):
    keys_chart = lead([0] * 6, notes=[{"t": 1.0, "s": 0, "f": 0}], name="Keys")
    files = {
        "arrangements/keys.json": keys_chart,
        "arrangements/lead.json": lead([-2, 0, 0, 0, 0, 0], notes=[{"t": 1.0, "s": 0, "f": 5}]),
    }
    manifest = manifest_for([-2, 0, 0, 0, 0, 0])
    manifest["arrangements"].insert(0, {"id": "keys", "name": "Keys", "type": "piano",
                                        "file": "arrangements/keys.json"})

    assert core.reference_entry(manifest, files)["id"] == "lead"
    report = core.retune_pack(manifest, files, 0, 2)

    assert report["from"] == "Drop D" and report["to"] == "E Standard"
    assert [a["id"] for a in report["arrangements"]] == ["lead"]
    assert files["arrangements/lead.json"]["notes"][0]["f"] == 3
    assert keys_chart["notes"][0]["f"] == 0
    assert "tuning" not in manifest["arrangements"][0]


def test_keys_chart_follows_the_audio_shift(core):
    keys_chart = lead([0] * 6, notes=[{"t": 1.0, "s": 2, "f": 23}, {"t": 2.0, "s": 2, "f": 12}],
                      chords=[{"t": 3.0, "id": 0, "notes": [{"s": 2, "f": 12}, {"s": 2, "f": 16}]}],
                      name="Keys")
    files = {"arrangements/keys.json": keys_chart, "arrangements/lead.json": lead([-1] * 6)}
    manifest = manifest_for([-1] * 6)
    manifest["arrangements"].append({"id": "keys", "name": "Keys", "type": "keys",
                                     "file": "arrangements/keys.json"})

    core.retune_pack(manifest, files, 1, 0)

    assert [(n["s"], n["f"]) for n in keys_chart["notes"]] == [(3, 0), (2, 13)]
    assert [(n["s"], n["f"]) for n in keys_chart["chords"][0]["notes"]] == [(2, 13), (2, 17)]
    assert "tuning" not in manifest["arrangements"][-1]


@pytest.mark.parametrize("kind,count,src", [("bass", 5, [0] * 5), ("guitar", 7, [0] * 7)])
def test_extended_range_low_b_is_not_dropped_with_the_guitar(core, kind, count, src):
    extra = {"id": "ext", "name": "Bass" if kind == "bass" else "Lead 7", "type": kind,
             "file": "arrangements/ext.json", "tuning": src}
    files = {
        "arrangements/lead.json": lead([0] * 6, notes=[{"t": 1.0, "s": 0, "f": 3}]),
        "arrangements/ext.json": lead(src, notes=[{"t": 1.0, "s": 0, "f": 3}], name=extra["name"]),
    }
    manifest = manifest_for([0] * 6)
    manifest["arrangements"].append(extra)

    core.retune_pack(manifest, files, 0, -2)

    assert manifest["arrangements"][0]["tuning"] == [-2, 0, 0, 0, 0, 0]
    assert extra["tuning"] == src
    assert files["arrangements/ext.json"]["notes"][0]["f"] == 3


def test_bass_in_the_same_tuning_drops_with_the_guitar(core):
    files = {"arrangements/lead.json": lead([0] * 6),
             "arrangements/bass.json": lead([0, 0, 0, 0], notes=[{"t": 1.0, "s": 0, "f": 3}], name="Bass")}
    manifest = manifest_for([0] * 6, [0, 0, 0, 0])

    core.retune_pack(manifest, files, 0, -2)

    assert manifest["arrangements"][1]["tuning"] == [-2, 0, 0, 0]
    assert files["arrangements/bass.json"]["notes"][0]["f"] == 5


def test_files_shared_by_two_arrangements_are_transformed_once(core):
    notation = {"version": 1, "measures": [{"idx": 1, "t": 0.0, "ks": 0, "staves": {"rh": {"voices": [
        {"v": 1, "beats": [{"t": 0.0, "dur": 4, "notes": [{"midi": 60}]}]}]}}}]}
    chart = lead([-2, 0, 0, 0, 0, 0], notes=[{"t": 1.0, "s": 0, "f": 5}])
    manifest = manifest_for([-2, 0, 0, 0, 0, 0])
    manifest["arrangements"].append({"id": "lead2", "name": "Lead 2", "file": "arrangements/lead.json",
                                     "tuning": [-2, 0, 0, 0, 0, 0]})
    for i in (1, 2):
        manifest["arrangements"].append({"id": f"keys{i}", "type": "piano",
                                         "notation": "arrangements/notation.json"})
    files = {"arrangements/lead.json": chart, "arrangements/notation.json": notation}

    report = core.retune_pack(manifest, files, 1, 2)

    assert chart["notes"][0]["f"] == 3
    assert report["chart"]["refretted"] == 1
    assert manifest["arrangements"][2]["tuning"] == [1, 1, 1, 1, 1, 1]
    assert notation["measures"][0]["staves"]["rh"]["voices"][0]["beats"][0]["notes"][0]["midi"] == 61
    assert notation["measures"][0]["ks"] == -5


def test_difficulty_levels_are_not_counted_twice(core):
    def level(difficulty):
        return {"difficulty": difficulty, "notes": [{"t": 1.0, "s": 0, "f": 5}], "chords": [],
                "anchors": [], "handshapes": []}

    phrases = [{"start_time": 0, "end_time": 5, "max_difficulty": 2, "levels": [level(0), level(1), level(2)]}]
    with_top = lead([-2, 0, 0, 0, 0, 0], notes=[{"t": 1.0, "s": 0, "f": 5}], phrases=copy.deepcopy(phrases))
    levels_only = lead([-2, 0, 0, 0, 0, 0], phrases=copy.deepcopy(phrases))

    for arrangement in (with_top, levels_only):
        report = core.retune_pack(manifest_for([-2, 0, 0, 0, 0, 0]),
                                  {"arrangements/lead.json": arrangement}, 0, 2)
        assert report["chart"]["refretted"] == 1
        assert [lv["notes"][0]["f"] for lv in arrangement["phrases"][0]["levels"]] == [3, 3, 3]


def test_capo_relative_frets_stay_playable_down_to_the_capo(core):
    notes = [{"t": 1.0, "s": 0, "f": 2}, {"t": 2.0, "s": 0, "f": 3}]
    files = {"arrangements/lead.json": lead([-2, 0, 0, 0, 0, 0], notes=notes)}
    manifest = manifest_for([-2, 0, 0, 0, 0, 0])
    manifest["arrangements"][0]["capo"] = 2

    core.retune_pack(manifest, files, 0, 2)

    assert [(n["s"], n["f"]) for n in files["arrangements/lead.json"]["notes"]] == [(0, 0), (0, 1)]


def test_capo_lowers_the_highest_playable_fret(core):
    notes = [{"t": 1.0, "s": 0, "f": 21}]
    files = {"arrangements/lead.json": lead([0] * 6, notes=notes)}
    manifest = manifest_for([0] * 6)
    manifest["arrangements"][0]["capo"] = 2

    report = core.retune_pack(manifest, files, 0, -2)

    note = files["arrangements/lead.json"]["notes"][0]
    assert (note["s"], note["f"]) == (1, 16)
    assert report["chart"]["relocated"] == 1
    assert core._highest_fret.get() == core.MAX_FRET


def bass(tuning, notes=None, chords=None, templates=None):
    return lead(tuning, notes=notes, chords=chords, templates=templates, name="Bass")


@pytest.mark.parametrize("kind,src,tgt,offset", [
    ("bass", 4, 5, 1), ("bass", 5, 6, 0), ("bass", 4, 6, 1), ("bass", 5, 4, -1),
    ("guitar", 6, 7, 1), ("guitar", 6, 8, 2), ("guitar", 7, 6, -1),
])
def test_string_alignment_matches_shared_open_strings(core, kind, src, tgt, offset):
    assert core.string_alignment(core.STANDARD_OPEN[(kind, src)], core.STANDARD_OPEN[(kind, tgt)]) == offset


def test_four_string_drop_d_bass_to_five_string_standard(core):
    notes = [{"t": 1.0, "s": 0, "f": 0}, {"t": 2.0, "s": 0, "f": 5}, {"t": 3.0, "s": 1, "f": 2}]
    chords = [{"t": 4.0, "id": 0, "notes": [{"s": 0, "f": 0}, {"s": 1, "f": 0}]}]
    templates = [{"name": "D5", "fingers": [0, 0, -1, -1], "frets": [0, 0, -1, -1]}]
    files = {
        "arrangements/lead.json": lead([-2, 0, 0, 0, 0, 0]),
        "arrangements/bass.json": bass([-2, 0, 0, 0], notes=notes, chords=chords, templates=templates),
    }
    manifest = manifest_for([-2, 0, 0, 0, 0, 0], [-2, 0, 0, 0])

    report = core.retune_pack(manifest, files, 0, 2, {"bass": 5})

    chart = files["arrangements/bass.json"]
    assert manifest["arrangements"][1]["tuning"] == [0, 0, 0, 0, 0]
    assert chart["tuning"] == [0, 0, 0, 0, 0]
    assert [(n["s"], n["f"]) for n in chart["notes"]] == [(0, 3), (1, 3), (2, 2)]
    assert [(n["s"], n["f"]) for n in chart["chords"][0]["notes"]] == [(0, 3), (2, 0)]
    assert chart["chords"][0]["id"] == 0
    assert chart["templates"] == [{"name": "D5", "fingers": [-1, -1, 0, -1, -1], "frets": [3, -1, 0, -1, -1]}]
    bass_report = report["arrangements"][1]
    assert (bass_report["from"], bass_report["to"]) == ("Drop D", "E Standard (5-string)")
    assert (bass_report["strings_from"], bass_report["strings_to"]) == (4, 5)
    assert bass_report["relocated"] == 2 and bass_report["octave_moved"] == 0
    assert report["label"] == "E Standard 5-string bass"


def test_drop_d_bass_becomes_five_string_standard_while_the_guitar_keeps_drop_d(core):
    guitar_notes = [{"t": 1.0, "s": 0, "f": 0}, {"t": 2.0, "s": 0, "f": 5}]
    bass_notes = [{"t": 1.0, "s": 0, "f": 0}, {"t": 2.0, "s": 0, "f": 5}]
    files = {
        "arrangements/lead.json": lead([-2, 0, 0, 0, 0, 0], notes=copy.deepcopy(guitar_notes)),
        "arrangements/bass.json": bass([-2, 0, 0, 0], notes=bass_notes),
    }
    manifest = manifest_for([-2, 0, 0, 0, 0, 0], [-2, 0, 0, 0])

    report = core.retune_pack(manifest, files, 0, 0, {"bass": 5})

    assert manifest["arrangements"][0]["tuning"] == [-2, 0, 0, 0, 0, 0]
    assert files["arrangements/lead.json"]["notes"] == guitar_notes
    assert manifest["arrangements"][1]["tuning"] == [0, 0, 0, 0, 0]
    assert [(n["s"], n["f"]) for n in files["arrangements/bass.json"]["notes"]] == [(0, 3), (1, 3)]
    assert report["label"] == "Drop D 5-string bass"
    assert report["arrangements"][1]["to"] == "E Standard (5-string)"


def test_adding_a_string_without_changing_the_tuning(core):
    notes = [{"t": 1.0, "s": 0, "f": 3, "fg": 1}, {"t": 2.0, "s": 3, "f": 7}]
    files = {
        "arrangements/lead.json": lead([0] * 6),
        "arrangements/bass.json": bass([0, 0, 0, 0], notes=notes),
    }
    manifest = manifest_for([0] * 6, [0, 0, 0, 0])

    report = core.retune_pack(manifest, files, 0, 0, {"bass": 5})

    assert [(n["s"], n["f"]) for n in files["arrangements/bass.json"]["notes"]] == [(1, 3), (4, 7)]
    assert files["arrangements/bass.json"]["notes"][0]["fg"] == 1
    assert manifest["arrangements"][1]["tuning"] == [0] * 5
    assert manifest["arrangements"][0]["tuning"] == [0] * 6
    assert report["chart"]["refretted"] == 0
    assert report["label"] == "E Standard 5-string bass"


def test_six_string_drop_d_guitar_to_seven_string_standard(core):
    notes = [{"t": 1.0, "s": 0, "f": 0}, {"t": 2.0, "s": 0, "f": 5}, {"t": 3.0, "s": 5, "f": 12}]
    files = {"arrangements/lead.json": lead([-2, 0, 0, 0, 0, 0], notes=notes)}

    core.retune_pack(manifest_for([-2, 0, 0, 0, 0, 0]), files, 0, 2, {"lead": 7})

    chart = files["arrangements/lead.json"]
    assert chart["tuning"] == [0] * 7
    assert [(n["s"], n["f"]) for n in chart["notes"]] == [(0, 3), (1, 3), (6, 12)]


def test_removing_the_low_b_moves_its_notes_to_the_e_string(core):
    notes = [{"t": 1.0, "s": 0, "f": 5}, {"t": 2.0, "s": 0, "f": 0}, {"t": 3.0, "s": 1, "f": 3}]
    entry = {"id": "bass", "name": "Bass", "type": "bass", "file": "arrangements/bass.json", "tuning": [0] * 5}
    manifest = manifest_for([0] * 6)
    manifest["arrangements"].append(entry)
    files = {"arrangements/lead.json": lead([0] * 6),
             "arrangements/bass.json": bass([0] * 5, notes=notes)}

    report = core.retune_pack(manifest, files, 0, 0, {"bass": 4})

    assert [(n["s"], n["f"]) for n in files["arrangements/bass.json"]["notes"]] == [(0, 0), (0, 7), (0, 3)]
    assert entry["tuning"] == [0] * 4
    assert report["chart"]["relocated"] == 1 and report["chart"]["octave_moved"] == 1


def test_six_string_bass_is_not_offered(core):
    entry = {"id": "bass", "name": "Bass", "type": "bass", "file": "arrangements/bass.json", "tuning": [0] * 5}
    manifest = manifest_for([0] * 6)
    manifest["arrangements"].append(entry)
    files = {"arrangements/lead.json": lead([0] * 6),
             "arrangements/bass.json": bass([0] * 5, notes=[{"t": 1.0, "s": 0, "f": 2}])}

    with pytest.raises(core.RetuneError, match="from 5 to 6"):
        core.retune_pack(manifest, files, 0, 0, {"bass": 6})


def test_zero_strings_is_rejected_not_treated_as_no_change(core):
    files = {"arrangements/lead.json": lead([0] * 6)}
    with pytest.raises(core.RetuneError, match="from 6 to 0"):
        core.retune_pack(manifest_for([0] * 6), files, 0, 0, {"lead": 0})


def test_added_string_on_an_unusual_tuning_sits_a_fourth_below(core):
    src = [-7, -7, -7, -7, -7, 0]
    assert core.tuning_family(src) == "other"
    files = {"arrangements/lead.json": lead(src, notes=[{"t": 1.0, "s": 0, "f": 0}])}

    core.retune_pack(manifest_for(src), files, 0, 0, {"lead": 7})

    tuning = files["arrangements/lead.json"]["tuning"]
    opens = [o + p for o, p in zip(core.STANDARD_OPEN[("guitar", 7)], tuning)]
    assert opens[1] - opens[0] == 5
    assert tuning[1:] == src


def test_lead_and_rhythm_extended_together_are_named_once(core):
    manifest = manifest_for([0] * 6)
    manifest["arrangements"].insert(1, {"id": "rhythm", "name": "Rhythm", "file": "arrangements/rhythm.json",
                                        "tuning": [0] * 6})
    files = {"arrangements/lead.json": lead([0] * 6), "arrangements/rhythm.json": lead([0] * 6, name="Rhythm")}

    report = core.retune_pack(manifest, files, 0, 0, {"lead": 7, "rhythm": 7})

    assert report["label"] == "E Standard (7-string)"


def test_string_count_requests_are_validated(core):
    files = {"arrangements/lead.json": lead([0] * 6), "arrangements/bass.json": bass([0, 0, 0, 0])}
    with pytest.raises(core.RetuneError, match="from 4 to 7"):
        core.retune_pack(manifest_for([0] * 6, [0, 0, 0, 0]), copy.deepcopy(files), 0, 0, {"bass": 7})
    with pytest.raises(core.RetuneError, match="Unknown"):
        core.retune_pack(manifest_for([0] * 6, [0, 0, 0, 0]), copy.deepcopy(files), 0, 0, {"keys": 5})
    with pytest.raises(core.RetuneError, match="same as the source"):
        core.retune_pack(manifest_for([0] * 6, [0, 0, 0, 0]), copy.deepcopy(files), 0, 0, {"bass": 4})


def test_requested_drop_with_an_extra_string_drops_the_new_lowest_string(core):
    notes = [{"t": 1.0, "s": 0, "f": 3}]
    files = {"arrangements/lead.json": lead([0] * 6, notes=notes)}

    report = core.retune_pack(manifest_for([0] * 6), files, 0, -2, {"lead": 7})

    assert files["arrangements/lead.json"]["tuning"] == [-2, 0, 0, 0, 0, 0, 0]
    assert (files["arrangements/lead.json"]["notes"][0]["s"], files["arrangements/lead.json"]["notes"][0]["f"]) == (1, 3)
    assert report["label"] == "Drop A (7-string)"


def test_requested_drop_with_a_removed_string_drops_the_new_lowest_string(core):
    entry = {"id": "lead", "name": "Lead", "file": "arrangements/lead.json", "tuning": [0] * 7}
    manifest = manifest_for([0] * 6)
    manifest["arrangements"][0] = entry
    files = {"arrangements/lead.json": lead([0] * 7, notes=[{"t": 1.0, "s": 1, "f": 5}])}

    report = core.retune_pack(manifest, files, 0, -2, {"lead": 6})

    assert entry["tuning"] == [-2, 0, 0, 0, 0, 0]
    assert (files["arrangements/lead.json"]["notes"][0]["s"], files["arrangements/lead.json"]["notes"][0]["f"]) == (0, 7)
    assert report["label"] == "Drop D"


def test_empty_tuning_is_not_refretted_by_the_audio_shift(core):
    manifest = manifest_for([0] * 6)
    manifest["arrangements"][0]["tuning"] = []
    files = {"arrangements/lead.json": lead([], notes=[{"t": 1.0, "s": 2, "f": 5}])}

    report = core.retune_pack(manifest, files, 2, 0)

    assert files["arrangements/lead.json"]["notes"][0]["f"] == 5
    assert report["chart"]["refretted"] == 0


def test_a_removed_note_does_not_block_its_old_string_number(core):
    plan = core.StringPlan([None, None, 1], [100, 28, 33], [28, 33])
    unplayable, relocatable = {"s": 0, "f": 0}, {"s": 1, "f": 0}
    report = core.ChartReport()

    kept, _ = core._place_group([unplayable, relocatable], plan, report, [], 1.0)

    assert kept == [relocatable]
    assert (relocatable["s"], relocatable["f"]) == (0, 0)
    assert report.removed == 1 and report.relocated == 1 and report.octave_moved == 0


def test_time_groups_chain_close_notes_within_a_two_millisecond_window(core):
    cluster = [{"t": 0.0}, {"t": 0.0008}, {"t": 0.0016}]
    run = [{"t": 1.0}, {"t": 1.0009}, {"t": 1.0018}, {"t": 1.0027}, {"t": 1.0036}]
    assert [[n["t"] for n in g] for g in core._time_groups(cluster)] == [[0.0, 0.0008, 0.0016]]
    assert [[n["t"] for n in g] for g in core._time_groups(run)] == [[1.0, 1.0009, 1.0018], [1.0027, 1.0036]]


def test_arrangements_sharing_a_chart_need_the_same_string_count(core):
    manifest = manifest_for([0] * 6, [-2, 0, 0, 0])
    manifest["arrangements"].insert(2, {"id": "bass2", "name": "Bass 2", "type": "bass",
                                        "file": "arrangements/bass.json", "tuning": [-2, 0, 0, 0]})
    files = {"arrangements/lead.json": lead([0] * 6),
             "arrangements/bass.json": bass([-2, 0, 0, 0], notes=[{"t": 1.0, "s": 0, "f": 0},
                                                                   {"t": 2.0, "s": 3, "f": 5}])}

    with pytest.raises(core.RetuneError, match="share a chart file"):
        core.retune_pack(copy.deepcopy(manifest), copy.deepcopy(files), 0, 0, {"bass": 5})
    report = core.retune_pack(manifest, files, 0, 0, {"bass": 5, "bass2": 5})

    assert [a["strings_to"] for a in report["arrangements"]] == [6, 5, 5]
    assert manifest["arrangements"][1]["tuning"] == [0] * 5
    assert manifest["arrangements"][2]["tuning"] == [0] * 5
    assert [a["to"] for a in report["arrangements"][1:]] == ["E Standard (5-string)"] * 2
    assert [(n["s"], n["f"]) for n in files["arrangements/bass.json"]["notes"]] == [(0, 3), (4, 5)]
    assert [(a["refretted"], a["relocated"]) for a in report["arrangements"][1:]] == [(1, 1), (1, 1)]
    assert (report["chart"]["refretted"], report["chart"]["relocated"]) == (1, 1)


def test_template_only_chord_keeps_its_note_when_a_string_is_added(core):
    templates = [{"name": "D5", "fingers": [0, 0, 0, -1, -1, -1], "frets": [0, 0, 0, -1, -1, -1]}]
    chords = [{"t": 1.0, "id": 0}]
    files = {"arrangements/lead.json": lead([-2, 0, 0, 0, 0, 0], chords=chords, templates=templates)}

    core.retune_pack(manifest_for([-2, 0, 0, 0, 0, 0]), files, 0, 0, {"lead": 7})

    assert files["arrangements/lead.json"]["templates"][0]["frets"] == [3, -1, 0, 0, -1, -1, -1]
    assert files["arrangements/lead.json"]["chords"][0]["id"] == 0


def test_template_only_chord_keeps_its_note_when_a_string_is_removed(core):
    entry = {"id": "lead", "name": "Lead", "file": "arrangements/lead.json", "tuning": [0] * 7}
    manifest = manifest_for([0] * 6)
    manifest["arrangements"][0] = entry
    templates = [{"name": "B", "frets": [0, -1, -1, -1, -1, -1, -1]}]
    files = {"arrangements/lead.json": lead([0] * 7, chords=[{"t": 1.0, "id": 0}], templates=templates)}

    core.retune_pack(manifest, files, 0, 0, {"lead": 6})

    assert files["arrangements/lead.json"]["templates"][0]["frets"] == [7, -1, -1, -1, -1, -1]


def test_padded_six_slot_bass_tuning_counts_its_real_strings(core):
    five = bass([0] * 6, notes=[{"t": 1.0, "s": 4, "f": 2}])
    four = bass([0] * 6, notes=[{"t": 1.0, "s": 1, "f": 2}])
    assert core.chart_string_count({"type": "bass"}, five) == 5
    assert core.chart_string_count({"type": "bass"}, four) == 4
    assert core.string_choices({"type": "bass"}, five) == [4, 5]


def test_label_comes_from_the_reference_even_without_ids(core):
    manifest = {"title": "S", "artist": "A", "duration": 1.0, "stems": [], "arrangements": [
        {"name": "Bass", "type": "bass", "file": "arrangements/bass.json", "tuning": [-3, -1, -1, -1]},
        {"name": "Lead", "file": "arrangements/lead.json", "tuning": [-1] * 6},
    ]}
    files = {"arrangements/bass.json": bass([-3, -1, -1, -1]), "arrangements/lead.json": lead([-1] * 6)}

    report = core.retune_pack(manifest, files, 1, 0)

    assert report["label"] == "E Standard"


def test_drop_target_keeps_its_drop_on_the_new_lowest_string(core):
    files = {"arrangements/lead.json": lead([-2, 0, 0, 0, 0, 0])}

    report = core.retune_pack(manifest_for([-2, 0, 0, 0, 0, 0]), files, -2, 0, {"lead": 7})

    assert files["arrangements/lead.json"]["tuning"] == [-4, -2, -2, -2, -2, -2, -2]
    assert report["label"] == "Drop G (7-string)"


def test_current_tuning_target_still_undrops_when_adding_a_string(core):
    files = {"arrangements/lead.json": lead([-2, 0, 0, 0, 0, 0])}

    report = core.retune_pack(manifest_for([-2, 0, 0, 0, 0, 0]), files, 0, 0, {"lead": 7})

    assert files["arrangements/lead.json"]["tuning"] == [0] * 7
    assert report["label"] == "E Standard (7-string)"


def test_chord_placement_replaces_the_shapes_own_relocation(core):
    entry = {"id": "lead", "name": "Lead", "file": "arrangements/lead.json", "tuning": [0] * 8}
    manifest = manifest_for([0] * 6)
    manifest["arrangements"][0] = entry
    templates = [{"name": "low", "frets": [0, 0, -1, -1, -1, -1, -1, -1]}]
    chords = [{"t": 1.0, "id": 0, "notes": [{"s": 1, "f": 0}]}]
    files = {"arrangements/lead.json": lead([0] * 8, chords=chords, templates=templates)}

    core.retune_pack(manifest, files, 0, 0, {"lead": 6})

    chart = files["arrangements/lead.json"]
    assert chart["templates"][0]["frets"] == [2, 2, -1, -1, -1, -1]
    assert [(n["s"], n["f"]) for n in chart["chords"][0]["notes"]] == [(0, 7)]
    assert chart["templates"][chart["chords"][0]["id"]]["frets"] == [7, -1, -1, -1, -1, -1]


def test_preview_mode_leaves_side_files_alone(core):
    notation = {"version": 1, "measures": [{"idx": 1, "t": 0.0, "ks": 0, "staves": {"rh": {"voices": [
        {"v": 1, "beats": [{"t": 0.0, "dur": 4, "notes": [{"midi": 60}]}]}]}}}]}
    manifest = manifest_for([-1] * 6, vocal_pitch="vocal_pitch.json")
    manifest["arrangements"].append({"id": "keys", "type": "piano", "notation": "notation.json"})
    files = {"arrangements/lead.json": lead([-1] * 6), "notation.json": notation,
             "vocal_pitch.json": {"version": 1, "notes": [{"t": 1.0, "d": 0.5, "midi": 63}]}}
    before = copy.deepcopy(files)

    report = core.retune_pack(manifest, files, 1, 0, side_files=False)

    assert report["to"] == "E Standard"
    assert files["notation.json"] == before["notation.json"]
    assert files["vocal_pitch.json"] == before["vocal_pitch.json"]


def test_nearest_target_uses_the_alignment_offset(core):
    shrink = core.StringPlan([None, None, 0, 1], [30, 35, 40, 45], [40, 45], offset=-2)
    grow = core.StringPlan([1, 2], [28, 33], [23, 28, 33], offset=1)
    assert [shrink.nearest_target(s) for s in range(4)] == [0, 0, 0, 1]
    assert grow.nearest_target(0) == 1


def test_eb_standard_bass_fits_a_standard_five_string_without_a_pitch_shift(core):
    notes = [{"t": 1.0, "s": 0, "f": 0}, {"t": 2.0, "s": 0, "f": 3}, {"t": 3.0, "s": 1, "f": 0},
             {"t": 4.0, "s": 3, "f": 5}]
    files = {"arrangements/lead.json": lead([-1] * 6),
             "arrangements/bass.json": bass([-1] * 4, notes=notes)}
    manifest = manifest_for([-1] * 6, [-1] * 4)

    report = core.retune_pack(manifest, files, 0, 0, {"bass": 5})

    assert manifest["arrangements"][1]["tuning"] == [0] * 5
    assert [(n["s"], n["f"]) for n in files["arrangements/bass.json"]["notes"]] == [(0, 4), (1, 2), (1, 4), (4, 4)]
    assert manifest["arrangements"][0]["tuning"] == [-1] * 6
    assert report["arrangements"][1]["to"] == "E Standard (5-string)"
    assert report["chart"]["octave_moved"] == 0


@pytest.mark.parametrize("src", [[-3, -1, -1, -1], [-2] * 4, [-5] * 4])
def test_lower_bass_tunings_also_fit_a_standard_five_string(core, src):
    files = {"arrangements/lead.json": lead([0] * 6),
             "arrangements/bass.json": bass(src, notes=[{"t": 1.0, "s": 0, "f": 0}])}
    manifest = manifest_for([0] * 6, src)

    report = core.retune_pack(manifest, files, 0, 0, {"bass": 5})

    assert manifest["arrangements"][1]["tuning"] == [0] * 5
    note = files["arrangements/bass.json"]["notes"][0]
    assert 23 + note["f"] == 28 + src[0]
    assert report["chart"]["octave_moved"] == 0


def test_a_bass_lower_than_the_new_low_string_keeps_its_tuning(core):
    files = {"arrangements/lead.json": lead([0] * 6), "arrangements/bass.json": bass([-7] * 4)}
    manifest = manifest_for([0] * 6, [-7] * 4)

    core.retune_pack(manifest, files, 0, 0, {"bass": 5})

    assert manifest["arrangements"][1]["tuning"] == [-7] * 5


def test_eb_standard_guitar_fits_a_standard_seven_string(core):
    files = {"arrangements/lead.json": lead([-1] * 6, notes=[{"t": 1.0, "s": 0, "f": 0}])}

    core.retune_pack(manifest_for([-1] * 6), files, 0, 0, {"lead": 7})

    assert files["arrangements/lead.json"]["tuning"] == [0] * 7
    assert [(n["s"], n["f"]) for n in files["arrangements/lead.json"]["notes"]] == [(0, 4)]


def test_explicit_tuning_target_still_decides_the_extended_tuning(core):
    files = {"arrangements/lead.json": lead([0] * 6), "arrangements/bass.json": bass([0] * 4)}
    manifest = manifest_for([0] * 6, [0] * 4)

    core.retune_pack(manifest, files, -1, 0, {"bass": 5})

    assert manifest["arrangements"][1]["tuning"] == [-1] * 5


def test_unused_guitar_shapes_in_a_bass_chart_do_not_count_as_strings(core):
    templates = [{"name": "Eb5", "frets": [12, -1, -1, -1, 12, 12]},
                 {"name": "power", "frets": [3, 5, -1, -1, -1, -1]}]
    chart = bass([-1] * 6, notes=[{"t": 1.0, "s": 3, "f": 2}],
                 chords=[{"t": 2.0, "id": 1, "notes": [{"s": 0, "f": 3}, {"s": 1, "f": 5}]}], templates=templates)
    entry = {"id": "bass", "name": "Bass", "type": "bass"}

    assert core.chart_string_count(entry, chart) == 4
    assert core.string_choices(entry, chart) == [4, 5]

    chart["handshapes"] = [{"chord_id": 0, "start_time": 1.0, "end_time": 2.0}]
    assert core.chart_string_count(entry, chart) == 6


def test_string_choices_per_instrument(core):
    assert core.string_choices({"type": "bass"}, bass([0, 0, 0, 0])) == [4, 5]
    assert core.string_choices({"type": "bass"}, bass([0] * 6, notes=[{"t": 1.0, "s": 5, "f": 0}])) == [6]
    assert core.string_choices({"name": "Lead"}, lead([0] * 6)) == [6, 7, 8]
    assert core.string_choices({"name": "Lead"}, lead([0] * 4)) == [4]
