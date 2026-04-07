# ComfyUI Save Image Extended — AdobeRGB TIFF16

A ComfyUI custom node for saving images with **true Adobe RGB (1998) color space conversion**, **embedded ICC profiles**, and **16-bit per channel** output. Supports PNG, TIFF, JPEG, WebP, AVIF, JXL, and more.

## What This Node Does

**Save Image Extended AdobeRGB** takes any image output in ComfyUI and saves it with proper color management. When you select Adobe RGB 1998, the node performs a real mathematical conversion from sRGB — it does not just tag the file with a different profile.

The conversion pipeline:

```
ComfyUI image (sRGB float)
    |
    v
Linearize (undo sRGB transfer function)
    |
    v
3x3 matrix transform (sRGB linear -> Adobe RGB linear, D65)
    |
    v
Clamp [0, 1]
    |
    v
Apply Adobe RGB gamma (563/256 = 2.19921875)
    |
    v
Quantize to 16-bit (0-65535) or 8-bit (0-255)
    |
    v
Encode TIFF/PNG with embedded ICC profile (tag 34675)
```

### Node Controls

| Parameter | Description |
|---|---|
| **color_space** | `sRGB` or `Adobe RGB 1998` — selects color pipeline and ICC profile |
| **bit_depth** | `8` or `16` — 16-bit available for PNG and TIFF only |
| **output_ext** | `.png`, `.tiff`, `.webp`, `.jpg`, `.jpeg`, `.j2k`, `.jp2`, `.gif`, `.bmp`, `.avif`, `.jxl` |
| **quality** | 0-100 — applies to lossy formats; PNG maps to compress level 0-9 |
| **filename_prefix** | Fixed string prefix for output filename |
| **filename_keys** | Comma-separated sampler keys for dynamic filenames (e.g. `sampler_name, cfg, steps`) |
| **foldername_prefix / foldername_keys** | Same templating for output subfolder structure |
| **save_metadata** | Embed prompt/workflow data into the file |
| **save_job_data** | Save generation parameters to `jobs.json` |
| **counter_digits / counter_position** | Auto-incrementing file counter (e.g. `0001`) |
| **named_keys** | Prefix values with key names in filename (e.g. `seed=123-cfg=7.5`) |

## What We Added

This node is based on [Save Image Extended](https://github.com/audioscavenger/save-image-extended-comfyui) by **AudioscavengeR** (original concept by @thedyze). The original node's TIFF output was broken and did not support color-managed workflows. We rebuilt the TIFF pipeline from scratch and added:

- **True sRGB to Adobe RGB (1998) color space conversion** — vectorized NumPy implementation with correct sRGB linearization, 3x3 chromaticity matrix (D65, no adaptation needed), and Adobe RGB gamma encoding using the exact value 563/256
- **Hand-built ICC v2.1 profile** — constructed from scratch in pure Python with all 9 required tags (`desc`, `wtpt`, `rXYZ`, `gXYZ`, `bXYZ`, `rTRC`, `gTRC`, `bTRC`, `cprt`), Bradford-adapted D50 primaries, and proper s15Fixed16 encoding
- **16-bit TIFF output** — via `tifffile` with ICC profile embedded as TIFF tag 34675
- **16-bit PNG output** — via `imagecodecs` with ICC profile injected as an `iCCP` chunk
- **8-bit ICC embedding** — all Pillow-based formats (JPEG, WebP, AVIF, JXL, TIFF 8-bit) receive the correct ICC profile
- **Fixed TIFF save** — the original node's TIFF export was non-functional; this version writes valid TIFF 6.0 files

All filename templating, folder generation, metadata embedding, and job data features from the original Save Image Extended are preserved.

## Related Projects

### Save-TIFF Node

Our standalone [ComfyUI Save TIFF](https://github.com/MushroomFleet/comfyui-save-tiff) node is a minimal, dependency-light TIFF saver (NumPy only — no Pillow required). It was developed alongside this project and shares the same color conversion math and ICC profile builder. The Save-TIFF node has been merged into this extended version, which adds multi-format support and the full filename templating system.

### Live Web Demo

Try the color conversion and TIFF export in your browser:
**[scuffedepoch.com/adobe-tiff16/](https://scuffedepoch.com/adobe-tiff16/)**

The web demo uses the same sRGB-to-Adobe-RGB pipeline (linearize, matrix, gamma) implemented in JavaScript, and generates downloadable 16-bit TIFF files with embedded ICC profiles — no installation required.

## Installation

### ComfyUI Manager

Search for **Save Image Extended AdobeRGB** in ComfyUI Manager and install.

### Manual

Clone into your ComfyUI custom nodes directory:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/MushroomFleet/ComfyUI-Save-Extended-TIFF16-adobe-rgb.git
pip install -r ComfyUI-Save-Extended-TIFF16-adobe-rgb/requirements.txt
```

### Dependencies

```
numpy
tifffile
imagecodecs
pillow
piexif
pillow-avif-plugin  (optional — enables AVIF)
pillow-jxl-plugin   (optional — enables JXL)
```

`tifffile` is required for 16-bit TIFF. `imagecodecs` is required for 16-bit PNG. If either is missing, the node falls back to 8-bit for that format.

## Credits

- **AudioscavengeR** — [Save Image Extended](https://github.com/audioscavenger/save-image-extended-comfyui) (original node, GPL-3.0). Filename templating, folder generation, metadata embedding, and multi-format save logic are derived from this project. Original concept by **@thedyze**.
- **Drift Johnson (MushroomFleet)** — Adobe RGB color conversion, ICC profile builder, 16-bit TIFF/PNG pipeline, TIFF fix.

## License

MIT

---

```
 ███▄ ▄███▓ █    ██   ██████  ██░ ██  ██▀███   ▒█████   ▒█████   ███▄ ▄███▓
▓██▒▀█▀ ██▒ ██  ▓██▒▒██    ▒ ▓██░ ██▒▓██ ▒ ██▒▒██▒  ██▒▒██▒  ██▒▓██▒▀█▀ ██▒
▓██    ▓██░▓██  ▒██░░ ▓██▄   ▒██▀▀██░▓██ ░▄█ ▒▒██░  ██▒▒██░  ██▒▓██    ▓██░
▒██    ▒██ ▓▓█  ░██░  ▒   ██▒░▓█ ░██ ▒██▀▀█▄  ▒██   ██░▒██   ██░▒██    ▒██
▒██▒   ░██▒▒▒█████▓ ▒██████▒▒░▓█▒░██▓░██▓ ▒██▒░ ████▓▒░░ ████▓▒░▒██▒   ░██▒
░ ▒░   ░  ░░▒▓▒ ▒ ▒ ▒ ▒▓▒ ▒ ░ ▒ ░░▒░▒░ ▒▓ ░▒▓░░ ▒░▒░▒░ ░ ▒░▒░▒░ ░ ▒░   ░  ░
░  ░      ░░░▒░ ░ ░ ░ ░▒  ░ ░ ▒ ░▒░ ░  ░▒ ░ ▒░  ░ ▒ ▒░   ░ ▒ ▒░ ░  ░      ░
░      ░     ░░ ░ ░ ░  ░  ░   ░  ░░ ░  ░░   ░ ░ ░ ░ ▒  ░ ░ ░ ▒  ░      ░
       ░      ░           ░   ░  ░     ░         ░ ░      ░ ░         ░

 ████████▓▒░  MushroomFleet  ░▒▓████████
```

---

## Support This Project

If you found this useful, please **star the repo** — it helps others discover it!

[![Star on GitHub](https://img.shields.io/github/stars/MushroomFleet/ComfyUI-Save-Extended-TIFF16-adobe-rgb?style=social)](https://github.com/MushroomFleet/ComfyUI-Save-Extended-TIFF16-adobe-rgb)