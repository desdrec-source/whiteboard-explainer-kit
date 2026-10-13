# Whiteboard Explainer kit

Starter kit for the Whiteboard Explainer bot. Built by Des Dreckett for the AI Video Motion community.

It renders a "phone video of a real whiteboard": an off-white board with an aluminium rim, a marker tray, ceiling glare, and a photographed hand holding a marker that draws every stroke. Text is written in a single-line font, and icons, ticks and crosses are drawn in black, green and red. Marker sound is optional. Everything is rendered in Python and piped to ffmpeg. No AI video model is involved.

## Quickstart

```bash
git clone https://github.com/desdrec-source/whiteboard-explainer-kit.git
cd whiteboard-explainer-kit
bash install.sh                                 # pip install, ffmpeg check, unpack assets
python3 -m wb.render examples/coached_vs_solo_16x9.json
# -> out/coached_vs_solo_16x9.mp4 (and out/coached_vs_solo_16x9_silent.mp4)
```

You can also use the zip: download https://github.com/desdrec-source/whiteboard-explainer-kit/archive/refs/heads/main.zip, unzip it, and run `bash install.sh`.

Requirements: Python 3.10+ and ffmpeg on PATH. Rendering is CPU-only and slow. A 40 s 1920x1080 video takes several minutes (about 0.5-1 s per frame), so run it in the background.

**Why `packed/`?** The binary assets (hand PNGs, marker WAVs, TTF fonts) are stored as base64 text chunks: the hands as lossless WebP and the sounds as FLAC. `install.sh` runs `tools/unpack_assets.py`, which rebuilds `assets/*.png`, `sfx/*.wav` and `fonts/*.ttf` bit-exactly and checks their SHA-256.

## Layout

```
wb/            renderer: render.py (layout, timeline, frames, ffmpeg), real.py (board, hands, Relief/Hershey text, IK arm),
               strokes.py (skeleton -> strokes), icons.py (polyline icons), sfx.py (marker sound)
examples/      rent_vs_buy_16x9.json, coached_vs_solo_16x9.json + the scripts that generate them
tools/         unpack_assets.py, verify_tip.py (nib/ink sync check), cut_hand_generic.py (make a new hand cut-out)
assets/fonts/  Relief SingleLine SVG font (OFL)
packed/        base64 chunks of the binary assets
```

## Making a new video

The easiest way is to copy an example generator and edit the texts and positions:

```bash
cp examples/make_coached_vs_solo_16x9_spec.py my_board.py   # edit the E(...) lines
python3 my_board.py 40 my_board.json                         # args: duration_s, output spec
python3 -m wb.render my_board.json
python3 tools/verify_tip.py my_board.json                    # optional: ink appears under the nib
```

The generators measure the real text widths (`RL.hershey_strokes`) so ticks and crosses sit right after the words. Use the `yfor()`/`captop()` helpers to line things up.

## Spec format (JSON)

Top-level keys used by the examples (style `photo8`):

| key | meaning |
|---|---|
| `aspect` | `"16:9"` (1920x1080) or `"9:16"` (1080x1920, default) |
| `duration` | seconds. Drawing speed is scaled to fit. |
| `style` | `"photo8"`: locked-off real-board look (recommended) |
| `font` | `"hershey:relief"`: Relief SingleLine capitals |
| `elements` | list, drawn in this order (see below) |
| `out` | output mp4 path (relative paths are relative to the current directory) |
| `hand` | `"default"`, `"deep"` or `"light_medium"` (see below), or a path to your own PNG |
| `hand_scale` | default-hand size (0.27 in landscape) |
| `pen_width`, `text_pen_scale`, `heading_size` | marker width in px/U (U = W/1080); thin smaller text |
| `letter_xscale` | letter width factor (about 0.85 for Relief) |
| `ink`, `ink_opacity`, `ink_unevenness` | RGB per colour name, opacity (1.15 = solid core), streakiness |
| `board` | `tray_h`, `floor`, `glare_y`, `glare_slope`, `glare_w`, `glare`, `albedo`, `tray_x` (marker slots), `eraser_x` |
| `hand_angle`, `pivot`, `pivot_gain` | locked-wrist arm: small rotation about an off-frame shoulder pivot |
| `arm_ik` | optional `{shoulder, l1, l2, cut}`: 2-bone IK forearm/upper-arm tube |
| `sleeve_rgb` | default hand's sweatshirt colour |
| `end_hold` | seconds to hold the finished board (default 3) |
| `sound`, `sfx_sources` | marker sound on/off; clips relative to the kit root |
| `voiceover` | optional WAV. Elements may carry `at: seconds` to start on cue, and the marker sound is ducked under the voice. |
| `seed` | randomness seed |
| `preview_times` | `[t, ...]`: render only those frames as PNGs (fast preview) |

Each element has a `type`, a `color` (`black`, `green`, `red`, `blue` or `[r,g,b]`) and an optional `area` (`top`, `left`, `right`, `bottom`):

- `{"type":"text","text":"COACHED","size":84,"x":0.26,"y":0.03,"anchor":"c"}`: x/y are fractions of the frame. `anchor` is `l` or `c`.
- `{"type":"icon","name":"tick","box":[x,y,w,h]}`: built-in icons are `tick cross arrow underline vline ellipse sun drop leaf key chain house building building8 house_outline house_door house_window house_chimney climb maze stick`.
- `{"type":"path","polylines":[[[x,y],...],...],"box":[x,y,w,h]}`: your own line art, with points in the unit box.
- `{"type":"image","path":"art.png","box":[...]}`: a clean dark-on-light line-art PNG, which gets skeletonised and traced.

## The `hand` option

| value | asset | look |
|---|---|---|
| `"default"` | `assets/hand_photo_cut.png` (Pexels 5310564) | grey sweatshirt sleeve restyle, ribbed cuff, watch |
| `"deep"` | `assets/hand_deep_cut.png` (Pexels 6209796) | deep skin tone, real black knit sleeve |
| `"light_medium"` | `assets/hand_light_medium_cut.png` (Pexels 8518882) | light-medium skin tone, bare forearm, rolled mustard sleeve |

Skin tones are as photographed. Nothing has been recoloured. Each preset in `wb/real.py` `HANDS` stores the nib pixel (`tip`), scale, the arm hand-over point to a generated tube (`band_c`, `axis`, `band_r`, `cut_al`, `tube_rgb`), `grade`, and the marker area that is recoloured to the ink (`marker_poly`, `nib_xmax`).

To add your own hand, download a licensed photo (for example from Pexels) of a right hand holding a marker, with the arm entering from the right or bottom-right, into `assets/src/`. Add an entry to `HANDSRC` in `tools/cut_hand_generic.py`, then run `pip install rembg` and `python3 tools/cut_hand_generic.py <name>` from the kit root. Next, add a `HANDS` entry with the nib pixel and check it on a `preview_times` frame.

## Motion rules baked in (why it looks real)

- **Static tray:** the tray, pens, eraser and rim are composited from one cached overlay with one fixed grain pattern, so they are pixel-identical in every frame. The marker in use is never removed from the tray, and there is no camera drift.
- **Area-based arm exits:** the hand leaves the frame only when it moves to a different area (`top`, `left`, `right`, `bottom`) and at the end. A colour change within an area is a short dip toward the bottom-right edge.
- **Locked wrist:** the hand moves by translation only. Rotation comes only from a small pivot about an off-frame shoulder (about ±5°). There is no tangent lean, spring wobble or pose switching. Travel between strokes is an eased arc.

## Licences

The code is MIT (see `LICENSE`). Every asset and its licence is listed in [LICENSES.md](LICENSES.md).
