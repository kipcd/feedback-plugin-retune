# Changelog

All notable changes to the Retune plugin are documented here.

## [Unreleased]

## [0.2.2]

### Changed

- **Change strings only** now lays added strings out in the instrument's standard tuning without
  touching the audio, whenever the song's lowest note still fits: a 4-string Eb Standard bass becomes
  a standard B E A D G 5-string, with every note re-fretted to keep its pitch. It used to keep the song's
  tuning, giving Bb Eb Ab Db Gb. Songs that go below the new lowest string keep the old behaviour.
- The target is labelled **no audio change (change strings only)**.

## [0.2.1]

### Changed

- The dialog starts on **current tuning (change strings only)**, so nothing changes until a tuning or
  string count is picked. It used to pre-select E Standard, which also converted every guitar when
  only a bass string count was meant to change.
- The preview and the result screen list every arrangement that changes, with its own counts
  (notes re-fretted, moved to another string, moved up an octave), instead of one combined total.

## [0.2.0]

### Added

- Convert guitar and bass arrangements to a different string count (bass 4/5, guitar 6/7/8), on
  its own or together with a tuning change. Strings are matched by their standard open notes, added
  low strings use standard tuning, and notes below the old low string move onto the new one instead
  of jumping an octave.
- **Current tuning (change strings only)** target, for conversions that only change the string count.
- The dialog previews the effect of the chosen tuning and string counts before converting
  (`GET /api/plugins/retune/preview`).

### Changed

- Converted packs whose string count changed are named after it, e.g.
  `<name>_Drop_D_5_string_bass.feedpak`.

## [0.1.0]

### Added

- **Retune…** library card action for feedpak songs: converts a song to another Standard, Drop or
  shifted tuning and writes the result as a new pack next to the original.
- Audio pitch-shift of every stem and the preview clip with ffmpeg (`rubberband` when available,
  resample fallback otherwise).
- Chart rewrite for low-string changes (Standard ↔ Drop): re-frets notes, chords, chord templates,
  hand shapes and phrase levels; relocates notes above fret 24 to the next string, moves notes
  below the new open low string up an octave, and widens anchors to cover the moved notes.
- Stems are re-encoded in their resolved codec (the manifest `codec` field wins over the extension).
- Transposition of notation, vocal pitch, vocal pitch contour, `keys.json` and `harmony.json`.
