# feedBack Plugin: Retune

Convert a feedpak song to another tuning. Retune pitch-shifts every audio stem and rewrites the
charts so the song plays in the tuning you're already in: Eb Standard → E Standard, Drop C → Drop D,
C Standard → Drop C, and so on. It can also convert a chart to a different number of strings, so a
4-string Drop D bass part plays on a 5-string bass in E Standard, or a 6-string part on a 7- or
8-string guitar.

The original song is never modified. The converted copy is written next to it as
`<name>_<Tuning>.feedpak` and shows up in the library straight away.

## How it works

1. Open the **⋮** menu on a feedpak song card in the Song Library and choose **Retune…**.

   <img src="docs/screenshots/menu.png" alt="Song card menu with the Retune… entry highlighted" width="206">

2. Pick the target tuning. The dialog says how the audio will be shifted and what happens to the
   chart, then **Convert** builds the new pack.

   <img src="docs/screenshots/picker.png" alt="Retune dialog converting Eb Standard to E Standard" width="560">

3. The converted song joins the original as another chart of the same song, so you can pick either
   version from the song's chart list.

   <img src="docs/screenshots/versions.png" alt="Song with two charts: the E Standard conversion and the Eb Standard original" width="560">

## What it can convert

Pick a target from the **Retune…** entry in a feedpak song card's menu. The plugin offers:

| From | To | Audio | Chart |
|---|---|---|---|
| any Standard | any other Standard (±7 semitones) | shifted | frets unchanged |
| any Drop | any other Drop | shifted | frets unchanged |
| a Standard | the Drop with the same top strings (E Std → Drop D, Eb Std → Drop C#…) | unchanged | low string re-fretted |
| a Standard / Drop | any Drop / Standard | shifted | low string re-fretted |
| any other tuning (Open G, DADGAD…) | the same tuning shifted up/down | shifted | frets unchanged |
| a 4/5-string bass or 6/7/8-string guitar | another string count of the same instrument | unchanged (unless combined with a tuning change) | notes moved to the matching strings |

### How the chart is rewritten

The audio moves by one shift for the whole song, chosen so the upper strings keep their frets. When
the low string changes relative to the others (Standard ↔ Drop), notes on it are re-fretted by ±2:

- Notes that land above fret 24 move to the next string up at the same pitch.
- Notes that would go below the open low string (e.g. an open D after Drop D → E Standard) move up an
  octave, since the new tuning can't play that pitch.
- Chord shapes, hand shapes, slides, multi-difficulty phrase levels and fingerings are updated to
  match. Fingerings on moved notes are cleared rather than guessed.

Other arrangements only have their low string changed when it matches the guitar's: same note, same
gap to the next string. A bass in Standard while the guitar is in Drop, or the low B of a 5-string
bass or 7-string guitar, keeps its tuning shape and only gets the audio shift.

Pitch data stored alongside the chart is transposed by the same shift: keys/piano charts, staff
notation (notes and key signatures), vocal pitch, the vocal pitch contour, `keys.json` and
`harmony.json`. Drum tabs, lyrics and
timing are unchanged.

### Changing the number of strings

Each guitar and bass arrangement can also be converted to a different string count: bass to 4 or 5
strings, guitar to 6, 7 or 8. This combines with the tuning target, or works on its own with the
**current tuning (change strings only)** target — for example a 4-string Drop D bass becomes a 5-string
bass in E Standard while the guitar stays in Drop D. Arrangements that share a chart file get one
string-count picker.

6-string bass isn't offered: feedBack can't tell a 6-string bass tuning from the 6-slot tuning older
charts pad every bass to, so a converted chart would display with the wrong number of strings.

- Strings are matched by their standard open notes, so a 4-string bass sits on the E A D G strings of
  a 5-string, and a 6-string guitar on the top six strings of a 7-string. Notes keep their pitch.
- With the current tuning or a Standard target, added low strings use standard tuning and a dropped
  low string goes back to standard: the new low string covers the notes the drop was for. Notes below
  the old low string move onto it (an open D becomes fret 3 on the B string) instead of jumping up an
  octave.
- With a Drop target (e.g. E Standard → Drop D, or Drop D → Drop C), the drop goes on the new lowest
  string, so a 6-string converted to a 7-string becomes Drop A or Drop G. The same applies when
  removing strings: a 7-string in Drop A becomes a 6-string in Drop D.
- Removing strings works too (5 → 4, 7 → 6); notes from the removed string move to the nearest
  string, or up an octave when they are below the new lowest string.

### Audio quality

Audio is shifted with ffmpeg's `rubberband` filter when available (the Docker image's ffmpeg build has
it), which keeps the tempo and sounds clean for shifts of a few semitones. Without rubberband the
plugin falls back to a resample-based shift and says so. Shifts beyond ±3 semitones are allowed but
flagged, because they start to sound processed.

## Installation

```bash
cd /path/to/feedBack/plugins
git clone https://github.com/kipcd/feedback-plugin-retune.git retune
```

Restart feedBack. The plugin needs `ffmpeg` on the server for any conversion that shifts the audio;
conversions that only re-fret the low string work without it.

## Limitations

- Only feedpak (`.feedpak` / `.sloppak`) songs are supported.
- Chord template names (e.g. `Em7`) are left as they are, since charts differ on whether they name
  the shape or the sounding chord.
- `manifest.yaml` is re-serialized, so comments in it are not preserved. Hand-edited `.jsonc`
  arrangement files are written back as plain JSON.

## Development

```bash
pip install pytest fastapi httpx pyyaml
pytest tests
```

The audio test runs only when `ffmpeg` is installed.

## License

MIT — see [LICENSE](LICENSE).
