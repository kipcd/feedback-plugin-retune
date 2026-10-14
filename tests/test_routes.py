import json
import shutil
import subprocess

import pytest

from conftest import dominant_frequency, read_pack, write_pack


def make_song(dlc_dir, tuning, audio=b"not-really-audio", chart_path="arrangements/lead.json",
              stem_path="stems/full.ogg", codec=None, include_chart=True):
    stem = {"id": "full", "file": stem_path, "default": True}
    if codec:
        stem["codec"] = codec
    manifest = {
        "title": "Song", "artist": "Band", "duration": 2.0,
        "arrangements": [{"id": "lead", "name": "Lead", "file": chart_path, "tuning": tuning}],
        "stems": [stem],
    }
    lead = {"name": "Lead", "tuning": tuning, "notes": [{"t": 0.5, "s": 0, "f": 0}],
            "chords": [], "anchors": [], "handshapes": [], "templates": []}
    files = {"stems/full.ogg": audio}
    if include_chart:
        files["arrangements/lead.json"] = lead
    (dlc_dir / "pack").mkdir(exist_ok=True)
    return write_pack(dlc_dir / "pack" / "Song.feedpak", manifest, files)


def run(client, **params):
    from urllib.parse import urlencode
    with client.websocket_connect(f"/ws/plugins/retune/run?{urlencode(params)}") as ws:
        while True:
            msg = ws.receive_json()
            if msg.get("done") or msg.get("error"):
                return msg


def test_options_lists_targets(client, dlc_dir):
    make_song(dlc_dir, [-2, 0, 0, 0, 0, 0])
    r = client.get("/api/plugins/retune/options", params={"filename": "pack/Song.feedpak"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"]["name"] == "Drop D"
    std = next(t for t in body["targets"] if t["name"] == "E Standard")
    assert (std["shift"], std["low_adjust"]) == (0, 2)
    assert all("chart" not in t for t in body["targets"])
    assert body["targets"][0]["keep"] is True
    assert body["arrangements"] == [
        {"ids": ["lead"], "name": "Lead", "kind": "guitar", "strings": 6, "choices": [6, 7, 8]}]


def make_band(dlc_dir):
    manifest = {
        "title": "Song", "artist": "Band", "duration": 2.0,
        "arrangements": [
            {"id": "lead", "name": "Lead", "file": "arrangements/lead.json", "tuning": [-2, 0, 0, 0, 0, 0]},
            {"id": "bass", "name": "Bass", "type": "bass", "file": "arrangements/bass.json",
             "tuning": [-2, 0, 0, 0]},
        ],
        "stems": [{"id": "full", "file": "stems/full.ogg", "default": True}],
    }
    chart = {"tuning": [-2, 0, 0, 0], "notes": [{"t": 0.5, "s": 0, "f": 0}], "chords": [],
             "anchors": [], "handshapes": [], "templates": []}
    return write_pack(dlc_dir / "Band.feedpak", manifest, {
        "arrangements/lead.json": dict(chart, name="Lead", tuning=[-2, 0, 0, 0, 0, 0]),
        "arrangements/bass.json": dict(chart, name="Bass"),
        "stems/full.ogg": b"audio",
    })


def test_arrangement_without_id_gets_no_string_picker(client, dlc_dir):
    manifest = {
        "title": "Song", "artist": "Band", "duration": 2.0,
        "arrangements": [{"name": "Lead", "file": "arrangements/lead.json", "tuning": [0] * 6}],
        "stems": [{"id": "full", "file": "stems/full.ogg", "default": True}],
    }
    write_pack(dlc_dir / "NoId.feedpak", manifest, {
        "arrangements/lead.json": {"tuning": [0] * 6, "notes": [{"t": 0.5, "s": 0, "f": 3}]},
        "stems/full.ogg": b"audio"})
    r = client.get("/api/plugins/retune/options", params={"filename": "NoId.feedpak"})
    assert r.status_code == 200, r.text
    assert r.json()["arrangements"][0]["choices"] == [6]


def test_arrangements_sharing_a_chart_get_one_picker(client, dlc_dir):
    manifest = {
        "title": "Song", "artist": "Band", "duration": 2.0,
        "arrangements": [
            {"id": "lead", "name": "Lead", "file": "arrangements/lead.json", "tuning": [0] * 6},
            {"id": "bass", "name": "Bass", "type": "bass", "file": "arrangements/bass.json", "tuning": [0] * 4},
            {"id": "bass2", "name": "Bass 2", "type": "bass", "file": "arrangements/bass.json", "tuning": [0] * 4},
        ],
        "stems": [{"id": "full", "file": "stems/full.ogg", "default": True}],
    }
    chart = {"tuning": [0] * 4, "notes": [{"t": 0.5, "s": 0, "f": 3}]}
    write_pack(dlc_dir / "Shared.feedpak", manifest, {
        "arrangements/lead.json": dict(chart, tuning=[0] * 6), "arrangements/bass.json": chart,
        "stems/full.ogg": b"audio"})

    body = client.get("/api/plugins/retune/options", params={"filename": "Shared.feedpak"}).json()

    assert [a["ids"] for a in body["arrangements"]] == [["lead"], ["bass", "bass2"]]
    assert body["arrangements"][1]["name"] == "Bass, Bass 2"
    r = client.get("/api/plugins/retune/preview", params={
        "filename": "Shared.feedpak", "strings": json.dumps({"bass": 5, "bass2": 5})})
    assert r.status_code == 200, r.text


def test_read_only_chart_loads_share_the_cached_copy(client, dlc_dir):
    from conftest import load_sibling
    routes = load_sibling("routes")
    src = make_song(dlc_dir, [-2, 0, 0, 0, 0, 0])

    first = routes._load_charts(src, mutable=False)
    second = routes._load_charts(src, mutable=False)

    assert first is second
    assert routes._load_charts(src)[0] is not first[0]


def test_chart_cache_returns_copies_and_follows_file_changes(client, dlc_dir):
    import os
    from conftest import load_sibling
    routes = load_sibling("routes")
    src = make_song(dlc_dir, [-2, 0, 0, 0, 0, 0])

    first, _ = routes._load_charts(src)
    first["arrangements"][0]["tuning"] = "mutated"
    second, _ = routes._load_charts(src)
    assert second["arrangements"][0]["tuning"] == [-2, 0, 0, 0, 0, 0]

    make_song(dlc_dir, [0] * 6)
    os.utime(src, ns=(1, 1))
    third, _ = routes._load_charts(src)
    assert third["arrangements"][0]["tuning"] == [0] * 6


def test_preview_reports_a_string_count_change(client, dlc_dir):
    make_band(dlc_dir)
    r = client.get("/api/plugins/retune/preview", params={
        "filename": "Band.feedpak", "shift": 0, "low_adjust": 2, "strings": json.dumps({"bass": 5})})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["label"] == "E Standard 5-string bass"
    bass = next(a for a in body["arrangements"] if a["id"] == "bass")
    assert (bass["to"], bass["strings_to"], bass["relocated"]) == ("E Standard (5-string)", 5, 1)


@pytest.mark.parametrize("strings", ['{"bass": 9}', "[5]", "not json"])
def test_preview_rejects_bad_string_counts(client, dlc_dir, strings):
    make_band(dlc_dir)
    r = client.get("/api/plugins/retune/preview", params={
        "filename": "Band.feedpak", "shift": 0, "low_adjust": 2, "strings": strings})
    assert r.status_code == 400


def test_run_converts_a_four_string_bass_to_five_strings(client, dlc_dir):
    make_band(dlc_dir)

    msg = run(client, filename="Band.feedpak", shift=0, low_adjust=2, strings=json.dumps({"bass": 5}))

    assert msg.get("done"), msg
    assert msg["filename"] == "Band_E_Standard_5_string_bass.feedpak"
    manifest, files = read_pack(dlc_dir / msg["filename"])
    assert manifest["arrangements"][1]["tuning"] == [0, 0, 0, 0, 0]
    assert manifest["arrangements"][0]["tuning"] == [0] * 6
    chart = json.loads(files["arrangements/bass.json"])
    assert (chart["notes"][0]["s"], chart["notes"][0]["f"]) == (0, 3)


@pytest.mark.parametrize("filename", ["../outside.feedpak", "/etc/passwd"])
def test_options_rejects_paths_outside_library(client, dlc_dir, filename):
    r = client.get("/api/plugins/retune/options", params={"filename": filename})
    assert r.status_code in (400, 404)


def test_low_string_only_retune_writes_new_pack_without_touching_audio(client, dlc_dir, indexed):
    src = make_song(dlc_dir, [-2, 0, 0, 0, 0, 0])
    original = src.read_bytes()

    msg = run(client, filename="pack/Song.feedpak", shift=0, low_adjust=2)

    assert msg.get("done"), msg
    assert msg["filename"] == "pack/Song_E_Standard.feedpak"
    assert src.read_bytes() == original
    manifest, files = read_pack(dlc_dir / msg["filename"])
    assert manifest["arrangements"][0]["tuning"] == [0] * 6
    lead = json.loads(files["arrangements/lead.json"])
    assert lead["tuning"] == [0] * 6
    assert (lead["notes"][0]["s"], lead["notes"][0]["f"]) == (0, 10)
    assert files["stems/full.ogg"] == b"not-really-audio"
    assert indexed and indexed[0][0] == "pack/Song_E_Standard.feedpak"


def test_invalid_target_reports_error(client, dlc_dir):
    make_song(dlc_dir, [0] * 6)
    msg = run(client, filename="pack/Song.feedpak", shift=0, low_adjust=0)
    assert "same as the source" in msg["error"]


def test_failed_conversion_leaves_no_partial_files(client, dlc_dir):
    make_song(dlc_dir, [-1] * 6, audio=b"not-really-audio")

    msg = run(client, filename="pack/Song.feedpak", shift=1, low_adjust=0)

    assert msg.get("error")
    assert sorted(p.name for p in (dlc_dir / "pack").iterdir()) == ["Song.feedpak"]


def test_successful_conversion_leaves_only_the_new_pack(client, dlc_dir):
    make_song(dlc_dir, [-2, 0, 0, 0, 0, 0])

    msg = run(client, filename="pack/Song.feedpak", shift=0, low_adjust=2)

    assert msg.get("done"), msg
    assert sorted(p.name for p in (dlc_dir / "pack").iterdir()) == ["Song.feedpak", "Song_E_Standard.feedpak"]


@pytest.mark.parametrize("mode", [0o644, 0o664])
def test_new_pack_gets_the_original_packs_permissions(client, dlc_dir, mode):
    import os
    src = make_song(dlc_dir, [-2, 0, 0, 0, 0, 0])
    os.chmod(src, mode)

    msg = run(client, filename="pack/Song.feedpak", shift=0, low_adjust=2)

    assert msg.get("done"), msg
    assert os.stat(dlc_dir / msg["filename"]).st_mode & 0o777 == mode


def drop_d_manifest(**extra):
    return {
        "title": "Song", "artist": "Band", "duration": 2.0,
        "arrangements": [{"id": "lead", "name": "Lead", "file": "arrangements/lead.json",
                          "tuning": [-2, 0, 0, 0, 0, 0]}],
        "stems": [{"id": "full", "file": "stems/full.ogg", "default": True}],
        **extra,
    }


DROP_D_CHART = {"name": "Lead", "tuning": [-2, 0, 0, 0, 0, 0], "notes": [{"t": 0.5, "s": 0, "f": 5}],
                "chords": [], "anchors": [], "handshapes": [], "templates": []}


def test_zip_members_stored_with_odd_names_are_found(client, dlc_dir):
    import yaml
    import zipfile
    with zipfile.ZipFile(dlc_dir / "Odd.feedpak", "w") as z:
        z.writestr("./manifest.yaml", yaml.safe_dump(drop_d_manifest()))
        z.writestr("./arrangements/lead.json", json.dumps(DROP_D_CHART))
        z.writestr("stems\\full.ogg", b"audio-bytes")

    msg = run(client, filename="Odd.feedpak", shift=0, low_adjust=2)

    assert msg.get("done"), msg
    with zipfile.ZipFile(dlc_dir / msg["filename"]) as z:
        assert sorted(z.namelist()) == ["arrangements/lead.json", "manifest.yaml", "stems/full.ogg"]
        assert json.loads(z.read("arrangements/lead.json"))["notes"][0]["f"] == 3
        assert z.read("stems/full.ogg") == b"audio-bytes"


def make_folder_pack(dlc_dir, stem_target):
    import yaml
    pack = dlc_dir / "Folder.feedpak"
    (pack / "arrangements").mkdir(parents=True)
    (pack / "stems").mkdir()
    (pack / "manifest.yaml").write_text(yaml.safe_dump(drop_d_manifest()))
    (pack / "arrangements" / "lead.json").write_text(json.dumps(DROP_D_CHART))
    (pack / "stems" / "full.ogg").symlink_to(stem_target)
    return pack


def test_symlinks_inside_a_folder_pack_are_followed(client, dlc_dir):
    import zipfile
    shared = dlc_dir / "Folder.feedpak" / "shared"
    shared.mkdir(parents=True)
    (shared / "mix.ogg").write_bytes(b"shared-audio")
    make_folder_pack(dlc_dir, shared / "mix.ogg")

    msg = run(client, filename="Folder.feedpak", shift=0, low_adjust=2)

    assert msg.get("done"), msg
    with zipfile.ZipFile(dlc_dir / msg["filename"]) as z:
        assert z.read("stems/full.ogg") == b"shared-audio"


def test_symlink_leaving_the_pack_is_reported_not_dropped(client, dlc_dir, tmp_path):
    outside = tmp_path / "outside.ogg"
    outside.write_bytes(b"secret")
    make_folder_pack(dlc_dir, outside)

    msg = run(client, filename="Folder.feedpak", shift=1, low_adjust=0)

    assert "stems/full.ogg" in msg["error"] and "missing" in msg["error"]
    assert sorted(p.name for p in dlc_dir.iterdir()) == ["Folder.feedpak"]


@pytest.mark.filterwarnings("ignore:Duplicate name")
def test_duplicate_zip_entries_use_the_last_copy_like_the_host(client, dlc_dir):
    import yaml
    import zipfile
    stale = dict(DROP_D_CHART, notes=[{"t": 0.5, "s": 0, "f": 9}])
    with zipfile.ZipFile(dlc_dir / "Dup.feedpak", "w") as z:
        z.writestr("manifest.yaml", yaml.safe_dump(drop_d_manifest()))
        z.writestr("arrangements/lead.json", json.dumps(stale))
        z.writestr("stems/full.ogg", b"audio-bytes")
        z.writestr("./arrangements/lead.json", json.dumps(DROP_D_CHART))

    msg = run(client, filename="Dup.feedpak", shift=0, low_adjust=2)

    assert msg.get("done"), msg
    with zipfile.ZipFile(dlc_dir / msg["filename"]) as z:
        assert z.namelist().count("arrangements/lead.json") == 1
        assert json.loads(z.read("arrangements/lead.json"))["notes"][0]["f"] == 3


def fake_ffmpeg(monkeypatch):
    from conftest import load_sibling
    audio_mod = load_sibling("audio_shift")

    def shift_file(ffmpeg, src, dst, shift, codec=None):
        dst.write_bytes(b"shifted:" + src.read_bytes())
        return "rubberband"

    monkeypatch.setattr(audio_mod, "find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(audio_mod, "shift_file", shift_file)


def test_missing_preview_is_skipped_not_fatal(client, dlc_dir, monkeypatch):
    fake_ffmpeg(monkeypatch)
    write_pack(dlc_dir / "NoPreview.feedpak", drop_d_manifest(preview="preview.ogg"),
               {"arrangements/lead.json": DROP_D_CHART, "stems/full.ogg": b"audio"})

    msg = run(client, filename="NoPreview.feedpak", shift=1, low_adjust=0)

    assert msg.get("done"), msg
    manifest, files = read_pack(dlc_dir / msg["filename"])
    assert files["stems/full.ogg"] == b"shifted:audio"
    assert "preview.ogg" not in files
    assert manifest["preview"] == "preview.ogg"


def test_legacy_full_mix_is_shifted_with_the_stems(client, dlc_dir, monkeypatch):
    fake_ffmpeg(monkeypatch)
    write_pack(dlc_dir / "Legacy.feedpak", drop_d_manifest(original_audio="./original/full.ogg"),
               {"arrangements/lead.json": DROP_D_CHART, "stems/full.ogg": b"stem",
                "original/full.ogg": b"mix"})

    msg = run(client, filename="Legacy.feedpak", shift=1, low_adjust=0)

    assert msg.get("done"), msg
    manifest, files = read_pack(dlc_dir / msg["filename"])
    assert files["original/full.ogg"] == b"shifted:mix"
    assert files["stems/full.ogg"] == b"shifted:stem"
    assert manifest["original_audio"] == "original/full.ogg"


def test_missing_legacy_full_mix_is_skipped(client, dlc_dir, monkeypatch):
    fake_ffmpeg(monkeypatch)
    write_pack(dlc_dir / "Legacy.feedpak", drop_d_manifest(original_audio="original/full.ogg"),
               {"arrangements/lead.json": DROP_D_CHART, "stems/full.ogg": b"stem"})

    msg = run(client, filename="Legacy.feedpak", shift=1, low_adjust=0)

    assert msg.get("done"), msg


def test_missing_stem_is_an_error(client, dlc_dir):
    write_pack(dlc_dir / "NoStem.feedpak", drop_d_manifest(), {"arrangements/lead.json": DROP_D_CHART})

    msg = run(client, filename="NoStem.feedpak", shift=1, low_adjust=0)

    assert "Audio file stems/full.ogg is listed in the manifest but missing" in msg["error"]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_audio_is_pitch_shifted(client, dlc_dir, tmp_path):
    tone = tmp_path / "tone.ogg"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=1", "-c:a", "libvorbis", str(tone)], check=True)
    make_song(dlc_dir, [-1] * 6, audio=tone.read_bytes())

    msg = run(client, filename="pack/Song.feedpak", shift=1, low_adjust=0)

    assert msg.get("done"), msg
    manifest, files = read_pack(dlc_dir / msg["filename"])
    assert manifest["arrangements"][0]["tuning"] == [0] * 6
    shifted = tmp_path / "shifted.ogg"
    shifted.write_bytes(files["stems/full.ogg"])
    assert dominant_frequency(shifted, 400, 520) == pytest.approx(466.16, rel=0.01)


def test_unnormalized_manifest_paths_are_still_rewritten(client, dlc_dir):
    make_song(dlc_dir, [-2, 0, 0, 0, 0, 0], chart_path="./arrangements//lead.json")

    msg = run(client, filename="pack/Song.feedpak", shift=0, low_adjust=2)

    assert msg.get("done"), msg
    manifest, files = read_pack(dlc_dir / msg["filename"])
    assert manifest["arrangements"][0]["file"] == "arrangements/lead.json"
    lead = json.loads(files["arrangements/lead.json"])
    assert lead["tuning"] == [0] * 6
    assert (lead["notes"][0]["s"], lead["notes"][0]["f"]) == (0, 10)


def test_missing_arrangement_file_is_a_clear_400(client, dlc_dir):
    make_song(dlc_dir, [-2, 0, 0, 0, 0, 0], include_chart=False)
    r = client.get("/api/plugins/retune/options", params={"filename": "pack/Song.feedpak"})
    assert r.status_code == 400
    assert "arrangements/lead.json" in r.json()["detail"]


def test_malformed_manifest_is_a_clear_400(client, dlc_dir):
    (dlc_dir / "Broken.feedpak").mkdir()
    (dlc_dir / "Broken.feedpak" / "manifest.yaml").write_text("title: [unclosed\n")
    r = client.get("/api/plugins/retune/options", params={"filename": "Broken.feedpak"})
    assert r.status_code == 400
    assert "not valid YAML" in r.json()["detail"]


def test_manifest_path_escaping_the_pack_is_rejected(client, dlc_dir):
    make_song(dlc_dir, [0] * 6, chart_path="../outside.json")
    r = client.get("/api/plugins/retune/options", params={"filename": "pack/Song.feedpak"})
    assert r.status_code == 400


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_declared_stem_codec_is_kept(client, dlc_dir, tmp_path):
    from conftest import ffprobe_codec
    from test_audio_shift import has_encoder, tone
    if not has_encoder("libopus"):
        pytest.skip("ffmpeg has no libopus")
    src = tone(tmp_path / "in.ogg", 440, 48000, ["-c:a", "libopus"])
    make_song(dlc_dir, [-1] * 6, audio=src.read_bytes(), codec="opus")

    msg = run(client, filename="pack/Song.feedpak", shift=1, low_adjust=0)

    assert msg.get("done"), msg
    manifest, files = read_pack(dlc_dir / msg["filename"])
    assert manifest["stems"][0]["codec"] == "opus"
    out = tmp_path / "out.ogg"
    out.write_bytes(files["stems/full.ogg"])
    assert ffprobe_codec(out) == "opus"
