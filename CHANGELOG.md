# Changelog

All notable changes to the Retune plugin are documented here.

## [Unreleased]

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
