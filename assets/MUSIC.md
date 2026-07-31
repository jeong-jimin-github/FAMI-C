# NES BGM arrangement

The ROM uses a deterministic four-voice 2A03 arrangement generated locally
from `C:\Users\jm\Downloads\slaop88c.mid`. The source MIDI itself is not copied
into this project or the ROM.

- Title metadata: `Give a reason`, version 3.5, by taka.S
- Source SHA-256: `52f3abcc37d01fe61954f825cb78112c1ebf122efc49c8f3c50b94ceabc44e82`
- Complete MIDI duration: 269.604819 seconds (`4:29.605`), beats 0-620
- Arranged musical section: beats 8-620, 266.126555 seconds (`4:26.127`)
- Grid: 2,448 sixteenth-note steps, 153 bars, normally 138 BPM
- Pulse 1 priority: Vocal, Bell, then the opening Synth 2 pickup
- Pulse 2: monophonic Synth 1 onsets
- Triangle: octave-folded Bass
- Noise: prioritized General MIDI drum reduction

The MIDI changes to 132 BPM at beat 492 and returns to 138 BPM one source tick
before beat 494. Its meter is 4/4 except for 2/4 bars at beats 492-494 and
590-592. The player represents the 492-494 tempo turn with its own half-bar
order entry.

## Musical sections

| Source beats | Section |
| --- | --- |
| 8-12 | Synth pickup |
| 12-44 | Intro A |
| 44-76 | Intro B |
| 76-84 | Intro break |
| 84-116 | Verse 1A |
| 116-164 | Verse 1B |
| 164-252 | Chorus 1 |
| 252-284 | Instrumental break |
| 284-332 | Verse 2B |
| 332-420 | Chorus 2 |
| 420-452 | Instrumental bridge |
| 452-492 | Vocal build |
| 492-496 | 2/4 tempo turn and turnaround |
| 496-562 | Final chorus and vocal cadence |
| 562-590 | Outro |
| 590-592 | 2/4 outro turn |
| 592-604 | Ending |
| 604-620 | Release tail |

The four arranged channels repeat exactly for source beats 164-248 and
332-416. This repetition is one reason the pattern dictionary is effective.

## ROM compression and C ABI

Each pattern contains eight steps, or one two-beat half-bar. Patterns are
deduplicated independently per channel. The 306 positions then deduplicate
their four pattern IDs into a shared 156-entry tuple dictionary.

Tonal patterns store one MIDI base pitch and four packed bytes. Each packed
byte contains two high-nibble-first steps: 0 is a rest and 1-15 is
`base + code - 1`. Nine Pulse 1 cells in the ending are moved down one octave
to keep every local pitch span encodable. Noise patterns use the same four
packed bytes directly with codes 0-6.

The generated pattern counts and byte costs are:

- Pulse 1: 77 patterns x 5 bytes = 385 bytes
- Pulse 2: 30 patterns x 5 bytes = 150 bytes
- Triangle: 47 patterns x 5 bytes = 235 bytes
- Noise: 70 patterns x 4 bytes = 280 bytes
- Four tuple planes: 156 x 4 bytes = 624 bytes
- Order pages: 256 + 50 bytes = 306 bytes
- Total: 1,980 bytes, down from 9,792 uncompressed bytes

`render_c_arrays()` emits exactly 25 arrays in this order:

```text
MUSIC_PULSE1_BASE[77]
MUSIC_PULSE1_PAIR0[77] ... MUSIC_PULSE1_PAIR3[77]
MUSIC_PULSE2_BASE[30]
MUSIC_PULSE2_PAIR0[30] ... MUSIC_PULSE2_PAIR3[30]
MUSIC_TRIANGLE_BASE[47]
MUSIC_TRIANGLE_PAIR0[47] ... MUSIC_TRIANGLE_PAIR3[47]
MUSIC_NOISE_PAIR0[70] ... MUSIC_NOISE_PAIR3[70]
MUSIC_TUPLE_PULSE1[156]
MUSIC_TUPLE_PULSE2[156]
MUSIC_TUPLE_TRIANGLE[156]
MUSIC_TUPLE_NOISE[156]
MUSIC_ORDER0[256]
MUSIC_ORDER1[50]
```

The JSON uses `fami-c-nes-arrangement-v2` and mirrors those pattern, tuple, and
order planes. IDs are assigned on first use, which makes regeneration stable.

Regenerate, verify, or exercise the in-memory codec tests with:

```powershell
python .\tools\arrange_midi.py --input "$HOME\Downloads\slaop88c.mid"
python .\tools\arrange_midi.py --input "$HOME\Downloads\slaop88c.mid" --check
python .\tools\arrange_midi.py --self-test
python .\tools\arrange_midi.py --input "$HOME\Downloads\slaop88c.mid" --embed-c .\examples\tetris.c
```

The source MIDI's embedded metadata says that unauthorized redistribution and
commercial use are prohibited. Keep ROMs containing this arrangement for
personal, non-commercial use unless permission has been obtained from the
relevant rights holders.
