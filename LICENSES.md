# Asset licences

All shipped assets can be redistributed, including commercially. The binary assets live in `packed/` and are restored by `install.sh`.

## Hands (Pexels License)
The Pexels License allows free use and modification, including commercial use, with no attribution required. It does not allow selling unaltered copies or redistributing the photos as a stock or wallpaper collection. Only modified cut-outs are shipped here, not the original photos. Credit is given anyway:

| file | source | photographer | changes |
|---|---|---|---|
| `assets/hand_photo_cut.png` (`hand: "default"`) | [Pexels 5310564](https://www.pexels.com/photo/crop-man-writing-on-whiteboard-in-modern-office-5310564/) "Crop man writing on whiteboard in modern office" | Malte Luk | Cut out with rembg (isnet-general-use) and manual nib/collar refinement. The sleeve beyond the wristband, the cuff and the watch are generated at render time. |
| `assets/hand_deep_cut.png` (`hand: "deep"`) | [Pexels 6209796](https://www.pexels.com/photo/a-person-in-black-sweater-holding-a-marker-while-writing-on-whiteboard-6209796/) "A Person in Black Sweater Holding a Marker while Writing on Whiteboard" | cottonbro studio | Cut out with rembg and refined in `tools/cut_hand_generic.py`. The arm past the elbow is a generated knit tube. |
| `assets/hand_light_medium_cut.png` (`hand: "light_medium"`) | [Pexels 8518882](https://www.pexels.com/photo/a-person-writing-on-white-board-8518882/) "A Person Writing on White Board" | Artem Podrez | Same pipeline, with a generated mustard sleeve extension. |

Skin tones are as photographed. Nothing has been recoloured.

## Fonts (SIL Open Font License 1.1)
- `assets/fonts/ReliefSingleLineSVG-Regular.svg`: Relief SingleLine, © 2022 The Relief SingleLine Project Authors, https://github.com/isdat-type/Relief-SingleLine. Licence: `assets/fonts/OFL-ReliefSingleLine.txt`.
- `fonts/PatrickHand-Regular.ttf`: Patrick Hand, © 2010-2012 Patrick Wagesreiter (Google Fonts). Licence: `fonts/OFL-PatrickHand.txt`.
- `fonts/Caveat-VariableFont_wght.ttf`: Caveat, © 2014 The Caveat Project Authors (Google Fonts). Licence: `fonts/OFL-Caveat.txt`.
- Hershey single-line fonts come from the `Hershey-Fonts` pip package (installed, not bundled). They use the Hershey font licence, which permits free use.

## Sounds (CC0 1.0, public domain)
- `sfx/marker_lines.wav`: "377124 tubbsmedia marker-lines.wav" by TubbsMedia, from Freesound #377124 via Wikimedia Commons. CC0 1.0.
- `sfx/bsb_0807_whiteboard_marker.wav`: "Whiteboard marker" by Joseph Sardin, BigSoundBank #807, https://bigsoundbank.com/whiteboard-marker-s0807.html. CC0.

## Board, tray, sleeve, icons
These are generated procedurally in code (`wb/real.py`, `wb/icons.py`). No third-party images are used.
