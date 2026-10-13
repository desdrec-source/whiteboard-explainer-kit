"""Rebuild the binary assets (hand PNGs, marker WAVs, TTF fonts) from packed/*.b64.NN.
Hands are stored as lossless WebP and sounds as FLAC; both decode bit-exactly to the originals."""
import base64, hashlib, io, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
man = json.load(open(os.path.join(ROOT, 'packed', 'manifest.json')))
for m in man:
    out = os.path.join(ROOT, m['out'])
    if os.path.exists(out) and '--force' not in sys.argv:
        print('ok  ', m['out']); continue
    b = base64.b64decode(''.join(open(os.path.join(ROOT, p)).read() for p in m['parts']))
    if hashlib.sha256(b).hexdigest() != m['sha256']: sys.exit('checksum mismatch: ' + m['packed'])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if m['packed'].endswith('.webp'):
        from PIL import Image; Image.open(io.BytesIO(b)).save(out, optimize=False)
    elif m['packed'].endswith('.flac'):
        import soundfile as sf
        info = sf.info(io.BytesIO(b)); y, sr = sf.read(io.BytesIO(b), dtype='int32')
        sf.write(out, y, sr, subtype=info.subtype if info.subtype.startswith('PCM') else 'PCM_24')
    else: open(out, 'wb').write(b)
    print('made', m['out'])
