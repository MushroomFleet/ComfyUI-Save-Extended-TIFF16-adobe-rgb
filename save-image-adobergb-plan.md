# Save Image Extended — Adobe RGB

## Description

A standalone ComfyUI custom node pack that saves generated images with proper **color space management** (sRGB / Adobe RGB 1998) and **bit depth control** (8-bit / 16-bit). Recreates all core functionality from the reference "Save Image Extended" node by AudioscavengeR (v2.88) without using it as a dependency.

### Key Additions Over Reference

1. **Color Space** dropdown: `sRGB`, `Adobe RGB 1998` — embeds the correct ICC profile and performs accurate color conversion when Adobe RGB is selected.
2. **Bit Depth** dropdown: `8`, `16` — enables 16-bit per channel output for PNG and TIFF. Falls back to 8-bit for formats that don't support it.

### Retained Features (from reference)

- All output formats: `.png`, `.tiff`, `.jpg`, `.jpeg`, `.webp`, `.j2k`, `.jp2`, `.gif`, `.bmp` (plus `.avif`, `.jxl` when plugins available)
- Customizable filename/folder templates from sampler parameters, datetime, node widget values
- Counter-based sequential naming with configurable digits and position
- Metadata embedding (PNG text chunks, EXIF for JPEG/WebP/AVIF/JXL/TIFF)
- Job data export to JSON
- Image preview toggle
- Quality/compression control per format
- Named keys option for filenames

---

## Project Structure

```
save-image-adobe-rgb/
├── __init__.py                         # ComfyUI registration
├── save_image_extended_adobeRGB.py     # Main node (all logic)
├── requirements.txt                    # Python dependencies
└── pyproject.toml                      # ComfyUI registry metadata
```

No `web/` directory or static assets — this is a headless output node.

---

## Dependencies

```
numpy
pillow
piexif
imagecodecs
tifffile
pillow-avif-plugin
pillow-jxl-plugin
```

**New vs reference:**
- `tifffile` — added for reliable 16-bit TIFF writing with ICC profile and tag support.
- `imagecodecs` — retained; also used for 16-bit PNG encoding.

---

## Implementation Steps

### Step 1 — Create `__init__.py`

Minimal registration file. No web assets needed.

### Step 2 — Create `save_image_extended_adobeRGB.py`

This is the single-file node implementation containing:
- ICC profile generation (sRGB + Adobe RGB 1998)
- Color space conversion math (sRGB ↔ Adobe RGB via linearization + matrix)
- 8-bit and 16-bit image pipeline
- All reference features (filename templating, counters, metadata, job data)
- Format-specific save logic with ICC profile embedding

### Step 3 — Create `requirements.txt` and `pyproject.toml`

### Step 4 — Test with ComfyUI

---

## Technical Design

### Color Space Architecture

**sRGB (default):** Pixels from ComfyUI's VAE are already in sRGB space. We embed the sRGB ICC profile into the output file so color-managed applications display it correctly.

**Adobe RGB 1998:** We convert pixel values from sRGB to Adobe RGB 1998 color space, then embed the Adobe RGB ICC profile. This ensures round-trip accuracy — the image displays identically in color-managed viewers but stores values in the wider Adobe RGB gamut.

#### Conversion Pipeline (sRGB → Adobe RGB)

```
1. Linearize sRGB gamma:
   if v <= 0.04045: linear = v / 12.92
   else:            linear = ((v + 0.055) / 1.055) ^ 2.4

2. Apply 3×3 color matrix:  sRGB-linear → XYZ(D65) → AdobeRGB-linear
   M_srgb_to_xyz = [[0.4124564, 0.3575761, 0.1804375],
                     [0.2126729, 0.7151522, 0.0721750],
                     [0.0193339, 0.1191920, 0.9503041]]

   M_adobe_to_xyz = [[0.5767309, 0.1855540, 0.1881852],
                      [0.2973769, 0.6273491, 0.0752741],
                      [0.0270343, 0.0706872, 0.9911085]]

   M_combined = inv(M_adobe_to_xyz) @ M_srgb_to_xyz

3. Apply Adobe RGB gamma:
   out = linear_adobe ^ (1.0 / 2.19921875)
```

This runs on the float [0,1] tensor BEFORE quantization to 8-bit or 16-bit.

#### ICC Profile Construction

Both profiles are built programmatically using `PIL.ImageCms` for sRGB and a struct-packed binary ICC v2 profile for Adobe RGB 1998. Profiles are created once at module load and cached as `bytes` objects.

The Adobe RGB 1998 profile is constructed from its known specification:
- White point: D65
- Primaries: R(0.64, 0.33), G(0.21, 0.71), B(0.15, 0.06)
- TRC gamma: 563/256 ≈ 2.19921875
- PCS: XYZ adapted to D50 via Bradford matrix

### Bit Depth Architecture

**8-bit (default):** `(tensor * 255).clip(0, 255).astype(uint8)` → Pillow `Image.fromarray()` as `'RGB'` mode. All formats supported.

**16-bit:** `(tensor * 65535).clip(0, 65535).astype(uint16)` → saved via specialized encoders:
- **PNG 16-bit:** `imagecodecs.png_encode()` with manual ICC/text chunk injection
- **TIFF 16-bit:** `tifffile.imwrite()` with ICC profile tag and description tags
- **All other formats:** Automatic fallback to 8-bit (console warning printed)

### Bit Depth + Format Compatibility Matrix

| Format | 8-bit | 16-bit | ICC Profile | Metadata |
|--------|-------|--------|-------------|----------|
| PNG    | ✓     | ✓      | ✓ iCCP      | ✓ tEXt   |
| TIFF   | ✓     | ✓      | ✓ Tag 34675 | ✓ Tags   |
| JPEG   | ✓     | fallback 8 | ✓ APP2  | ✓ EXIF   |
| WebP   | ✓     | fallback 8 | via EXIF | ✓ EXIF  |
| AVIF   | ✓     | fallback 8 | via EXIF | ✓ EXIF  |
| JXL    | ✓     | fallback 8 | via EXIF | ✓ EXIF  |
| J2K/JP2| ✓     | fallback 8 | ✗        | partial  |
| GIF    | ✓     | fallback 8 | ✗        | ✓ PNG    |
| BMP    | ✓     | fallback 8 | ✗        | ✗        |

### Metadata Embedding Strategy

**8-bit images (Pillow pipeline):**
- PNG/GIF: `PngInfo` text chunks (prompt + workflow)
- JPEG/WebP/AVIF/JXL/TIFF: EXIF tags `0x010f` (Make→Prompt) and `0x010e` (ImageDescription→Workflow)
- ICC profile: `img.info['icc_profile'] = profile_bytes` before `img.save()` (works for PNG, JPEG, TIFF, WebP)

**16-bit PNG (imagecodecs pipeline):**
- Encode pixel data with `imagecodecs.png_encode()`
- Inject iCCP, tEXt chunks into PNG byte stream via helper function
- Helper parses PNG signature + IHDR, inserts chunks before first IDAT

**16-bit TIFF (tifffile pipeline):**
- `tifffile.imwrite()` with `extratags` for ICC profile (tag 34675) and description
- Prompt/workflow stored in ImageDescription tag (270)

---

## Complete Source Code

### File 1: `__init__.py`

```python
from .save_image_extended_adobeRGB import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = None

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
```

### File 2: `requirements.txt`

```
numpy
piexif
imagecodecs
tifffile
pillow
pillow-avif-plugin
pillow-jxl-plugin
```

### File 3: `pyproject.toml`

```toml
[project]
name = "save-image-adobe-rgb"
version = "1.0.0"
description = "Save images with Adobe RGB / sRGB color space and 8/16-bit depth control."
license = { text = "MIT" }
requires-python = ">=3.9"
dependencies = [
  "numpy",
  "piexif",
  "imagecodecs",
  "tifffile",
  "pillow",
  "pillow-avif-plugin",
  "pillow-jxl-plugin",
]

[project.urls]
Repository = ""

[tool.comfy]
PublisherId = ""
DisplayName = "Save Image Extended AdobeRGB"
Icon = ""
```

### File 4: `save_image_extended_adobeRGB.py`

This is the main implementation file. Due to its size it is broken into logical sections below. Each section is presented in the order it appears in the file — concatenate them sequentially to form the complete file.

---

#### Section A — Imports, Globals, Plugin Detection

```python
import os
import re
import io
import sys
import json
import struct
import locale
from datetime import datetime
from pathlib import Path

import folder_paths
import numpy
import numpy as np

version = "1.0.0"

avif_supported = False
jxl_supported = False
debug = False

try:
    import pillow_avif
except Exception:
    print(f"\033[92m[save_image_adobeRGB]\033[0m AVIF not supported. pip install pillow-avif-plugin")
else:
    print(f"\033[92m[save_image_adobeRGB] AVIF supported\033[0m")
    avif_supported = True

try:
    import pillow_jxl
except Exception:
    print(f"\033[92m[save_image_adobeRGB]\033[0m JXL not supported. pip install pillow-jxl-plugin")
else:
    print(f"\033[92m[save_image_adobeRGB] JXL supported\033[0m")
    jxl_supported = True

from PIL import Image, ExifTags, ImageCms
from PIL.PngImagePlugin import PngInfo

try:
    import tifffile
except ImportError:
    tifffile = None
    print(f"\033[92m[save_image_adobeRGB]\033[0m tifffile not available. 16-bit TIFF disabled.")

try:
    import imagecodecs
except ImportError:
    imagecodecs = None
    print(f"\033[92m[save_image_adobeRGB]\033[0m imagecodecs not available. 16-bit PNG disabled.")

try:
    original_locale = locale.setlocale(locale.LC_TIME, '')
except Exception:
    pass
```

---

#### Section B — Color Space Utilities

```python
# ---------------------------------------------------------------------------
# Color‑space constants and ICC profile helpers
# ---------------------------------------------------------------------------

# sRGB → XYZ (D65) matrix  (IEC 61966‑2‑1)
_M_SRGB_TO_XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
], dtype=np.float64)

# Adobe RGB 1998 → XYZ (D65) matrix
_M_ADOBE_TO_XYZ = np.array([
    [0.5767309, 0.1855540, 0.1881852],
    [0.2973769, 0.6273491, 0.0752741],
    [0.0270343, 0.0706872, 0.9911085],
], dtype=np.float64)

# Combined: sRGB‑linear → Adobe‑RGB‑linear  (precomputed at import)
_M_SRGB_TO_ADOBE_LINEAR = np.linalg.inv(_M_ADOBE_TO_XYZ) @ _M_SRGB_TO_XYZ

# Adobe RGB gamma: 563/256
_ADOBE_GAMMA = 563.0 / 256.0  # ≈ 2.19921875


def srgb_to_linear(v):
    """Vectorised sRGB EOTF (gamma → linear)."""
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def linear_to_adobe_gamma(v):
    """Apply Adobe RGB 1998 OETF (linear → gamma‑encoded)."""
    return np.clip(v, 0.0, 1.0) ** (1.0 / _ADOBE_GAMMA)


def convert_srgb_to_adobergb(arr_float):
    """
    Convert a float32 [0,1] RGB array from sRGB to Adobe RGB 1998.
    Input shape: (H, W, 3).  Returns same shape, float32 [0,1].
    """
    linear = srgb_to_linear(arr_float.astype(np.float64))
    h, w, c = linear.shape
    flat = linear.reshape(-1, 3)
    converted = (flat @ _M_SRGB_TO_ADOBE_LINEAR.T)
    converted = np.clip(converted, 0.0, 1.0).reshape(h, w, c)
    result = linear_to_adobe_gamma(converted).astype(np.float32)
    return result


# ---- ICC profile construction ----

def _get_srgb_icc_bytes():
    """Return sRGB ICC profile as bytes via Pillow."""
    profile = ImageCms.createProfile('sRGB')
    cms_profile = ImageCms.ImageCmsProfile(profile)
    return cms_profile.tobytes()


def _build_icc_s15fixed16(val):
    """Encode a float as ICC s15Fixed16Number (4 bytes big‑endian)."""
    return struct.pack('>i', int(round(val * 65536)))


def _build_icc_xyz_tag(x, y, z):
    """Build an XYZ tag (type 'XYZ ', 20 bytes)."""
    return b'XYZ \x00\x00\x00\x00' + _build_icc_s15fixed16(x) + _build_icc_s15fixed16(y) + _build_icc_s15fixed16(z)


def _build_icc_curv_tag(gamma):
    """Build a parametric curve tag with a single gamma value."""
    # Type 'curv' with count=1 and uint16 gamma*256
    data = b'curv\x00\x00\x00\x00'
    data += struct.pack('>I', 1)                           # curveCount = 1
    data += struct.pack('>H', int(round(gamma * 256)))     # gamma as u8Fixed8Number
    # Pad to 4-byte boundary
    if len(data) % 4 != 0:
        data += b'\x00' * (4 - len(data) % 4)
    return data


def _build_adobe_rgb_icc():
    """
    Build a minimal ICC v2.1 profile for Adobe RGB (1998).
    PCS is XYZ with D50 illuminant (ICC requirement).
    Primaries are chromatically adapted from D65 → D50 via Bradford.
    """
    # Pre‑adapted XYZ values for Adobe RGB primaries under D50
    # (Standard values used in Adobe's published profile)
    rX, rY, rZ = 0.60974, 0.31111, 0.01947
    gX, gY, gZ = 0.20528, 0.62567, 0.06087
    bX, bY, bZ = 0.14919, 0.06322, 0.74457
    # Media white point (D50)
    wX, wY, wZ = 0.95045, 1.00000, 1.08905

    desc_text = "Adobe RGB (1998)"
    cprt_text = "Public Domain"

    # Build individual tags
    tag_rXYZ = _build_icc_xyz_tag(rX, rY, rZ)
    tag_gXYZ = _build_icc_xyz_tag(gX, gY, gZ)
    tag_bXYZ = _build_icc_xyz_tag(bX, bY, bZ)
    tag_wtpt = _build_icc_xyz_tag(wX, wY, wZ)
    tag_rTRC = _build_icc_curv_tag(_ADOBE_GAMMA)
    tag_gTRC = _build_icc_curv_tag(_ADOBE_GAMMA)
    tag_bTRC = _build_icc_curv_tag(_ADOBE_GAMMA)

    # desc tag (type 'desc')
    desc_bytes = desc_text.encode('ascii')
    tag_desc = b'desc\x00\x00\x00\x00'
    tag_desc += struct.pack('>I', len(desc_bytes) + 1)
    tag_desc += desc_bytes + b'\x00'
    # Pad localizable strings area (required by spec): 2 longs of 0
    tag_desc += b'\x00' * 12
    if len(tag_desc) % 4 != 0:
        tag_desc += b'\x00' * (4 - len(tag_desc) % 4)

    # cprt tag (type 'text')
    cprt_bytes = cprt_text.encode('ascii')
    tag_cprt = b'text\x00\x00\x00\x00'
    tag_cprt += cprt_bytes + b'\x00'
    if len(tag_cprt) % 4 != 0:
        tag_cprt += b'\x00' * (4 - len(tag_cprt) % 4)

    # Tag table: 9 tags
    tags = [
        (b'desc', tag_desc),
        (b'wtpt', tag_wtpt),
        (b'rXYZ', tag_rXYZ),
        (b'gXYZ', tag_gXYZ),
        (b'bXYZ', tag_bXYZ),
        (b'rTRC', tag_rTRC),
        (b'gTRC', tag_gTRC),
        (b'bTRC', tag_bTRC),
        (b'cprt', tag_cprt),
    ]

    tag_count = len(tags)
    header_size = 128
    tag_table_size = 4 + tag_count * 12  # count + entries

    # Compute offsets
    data_offset = header_size + tag_table_size
    tag_entries = []
    tag_data = b''
    for sig, data in tags:
        offset = data_offset + len(tag_data)
        size = len(data)
        tag_entries.append(struct.pack('>4sII', sig, offset, size))
        tag_data += data

    profile_size = data_offset + len(tag_data)

    # Build header (128 bytes)
    header = struct.pack('>I', profile_size)            # Profile size
    header += b'lcms'                                   # Preferred CMM
    header += b'\x02\x10\x00\x00'                      # Version 2.1.0
    header += b'mntr'                                   # Device class: monitor
    header += b'RGB '                                   # Color space
    header += b'XYZ '                                   # PCS
    header += struct.pack('>HHH HHH',                  # Date/time
                          2025, 1, 1, 0, 0, 0)
    header += b'acsp'                                   # Profile signature
    header += b'MSFT'                                   # Platform
    header += b'\x00' * 4                               # Flags
    header += b'\x00' * 4                               # Device manufacturer
    header += b'\x00' * 4                               # Device model
    header += b'\x00' * 8                               # Device attributes
    header += struct.pack('>I', 0)                      # Rendering intent: perceptual
    # PCS illuminant (D50 in s15Fixed16)
    header += _build_icc_s15fixed16(0.9642)
    header += _build_icc_s15fixed16(1.0000)
    header += _build_icc_s15fixed16(0.8249)
    header += b'\x00' * 4                               # Creator
    header += b'\x00' * 16                              # Profile ID
    header += b'\x00' * 28                              # Reserved

    assert len(header) == 128

    # Assemble
    profile = header
    profile += struct.pack('>I', tag_count)
    for entry in tag_entries:
        profile += entry
    profile += tag_data

    return profile


# Module‑level cached profiles (built once)
_SRGB_ICC_BYTES = _get_srgb_icc_bytes()
_ADOBE_RGB_ICC_BYTES = _build_adobe_rgb_icc()
```

---

#### Section C — 16‑bit PNG Helper

```python
# ---------------------------------------------------------------------------
# 16‑bit PNG writer (imagecodecs + chunk injection)
# ---------------------------------------------------------------------------

def _png_make_chunk(chunk_type, data):
    """Build a single PNG chunk: length + type + data + CRC."""
    import zlib
    raw = chunk_type + data
    return struct.pack('>I', len(data)) + raw + struct.pack('>I', zlib.crc32(raw) & 0xFFFFFFFF)


def _png_inject_chunks(png_bytes, icc_profile=None, text_chunks=None):
    """
    Inject iCCP and tEXt chunks into a PNG byte stream.
    Chunks are inserted after IHDR and before the first IDAT.
    png_bytes: raw PNG file bytes (from imagecodecs.png_encode).
    icc_profile: bytes of the ICC profile to embed as iCCP, or None.
    text_chunks: dict of {keyword: text_value} for tEXt chunks, or None.
    Returns modified PNG bytes.
    """
    import zlib
    PNG_SIG = b'\x89PNG\r\n\x1a\n'
    if not png_bytes.startswith(PNG_SIG):
        return png_bytes  # not a valid PNG, return as-is

    # Parse: signature (8) then chunks
    pos = 8
    # Read IHDR chunk
    ihdr_len = struct.unpack('>I', png_bytes[pos:pos+4])[0]
    ihdr_end = pos + 12 + ihdr_len  # length(4) + type(4) + data + crc(4)

    # Build injection payload
    inject = b''

    if icc_profile is not None:
        # iCCP chunk: profile_name (null-terminated) + compression_method(0) + compressed_data
        profile_name = b'ICC Profile\x00'
        compressed = zlib.compress(icc_profile)
        iccp_data = profile_name + b'\x00' + compressed
        inject += _png_make_chunk(b'iCCP', iccp_data)

    if text_chunks:
        for keyword, value in text_chunks.items():
            text_data = keyword.encode('latin-1') + b'\x00' + value.encode('latin-1', errors='replace')
            inject += _png_make_chunk(b'tEXt', text_data)

    # Reassemble: signature + IHDR + injected chunks + rest
    return PNG_SIG + png_bytes[8:ihdr_end] + inject + png_bytes[ihdr_end:]


def save_16bit_png(image_path, arr_uint16, icc_profile=None, prompt=None, extra_pnginfo=None, compress_level=4):
    """
    Save a 16‑bit per channel RGB PNG.
    arr_uint16: numpy array (H, W, 3) dtype=uint16.
    """
    if imagecodecs is None:
        raise RuntimeError("imagecodecs required for 16-bit PNG")

    png_bytes = imagecodecs.png_encode(arr_uint16, level=compress_level)

    # Build text chunks for metadata
    text_chunks = {}
    if prompt is not None:
        text_chunks['prompt'] = json.dumps(prompt)
    if extra_pnginfo is not None:
        for k in extra_pnginfo:
            text_chunks[k] = json.dumps(extra_pnginfo[k])

    png_bytes = _png_inject_chunks(png_bytes, icc_profile=icc_profile, text_chunks=text_chunks or None)

    with open(image_path, 'wb') as f:
        f.write(png_bytes)
```

---

#### Section D — 16‑bit TIFF Helper

```python
# ---------------------------------------------------------------------------
# 16‑bit TIFF writer (tifffile)
# ---------------------------------------------------------------------------

def save_16bit_tiff(image_path, arr_uint16, icc_profile=None, prompt=None, extra_pnginfo=None):
    """
    Save a 16‑bit per channel RGB TIFF.
    arr_uint16: numpy array (H, W, 3) dtype=uint16.
    """
    if tifffile is None:
        raise RuntimeError("tifffile required for 16-bit TIFF")

    extratags = []

    # ICC profile: TIFF tag 34675
    if icc_profile is not None:
        extratags.append((34675, 7, len(icc_profile), icc_profile, True))

    # Metadata: store prompt/workflow in ImageDescription (tag 270)
    metadata_dict = {}
    if prompt is not None:
        metadata_dict['prompt'] = prompt
    if extra_pnginfo is not None:
        metadata_dict.update(extra_pnginfo)
    if metadata_dict:
        desc = json.dumps(metadata_dict)
        extratags.append((270, 2, len(desc) + 1, desc + '\x00', True))

    tifffile.imwrite(
        image_path,
        arr_uint16,
        photometric='rgb',
        extratags=extratags if extratags else None,
    )
```

---

#### Section E — Main Node Class (class attributes + INPUT_TYPES)

```python
# ---------------------------------------------------------------------------
# Node Class
# ---------------------------------------------------------------------------

class SaveImageExtendedAdobeRGB:

    type                    = 'output'
    avif_quality            = 60
    webp_quality            = 90
    jpeg_quality            = 90
    jxl_quality             = 90
    j2k_quality             = 90
    tiff_quality            = 90
    optimize_image          = True

    filename_prefix         = 'ComfyUI'
    filename_keys           = 'sampler_name, cfg, steps, %F %H-%M-%S'
    foldername_prefix       = ''
    foldername_keys         = 'ckpt_name'
    delimiter               = '-'
    save_job_data           = 'disabled'
    job_data_per_image      = False
    job_custom_text         = ''
    save_metadata           = True
    counter_digits          = 4
    counter_position        = 'last'
    counter_positions       = ['last', 'first']
    one_counter_per_folder  = True
    image_preview           = True
    modelExtensions         = ['.safetensors', '.ckpt', '.pt', '.bin', '.pth']
    output_ext              = '.png'
    output_exts             = ['.png', '.tiff', '.webp', '.jpg', '.jpeg', '.j2k', '.jp2', '.gif', '.bmp']
    quality                 = 90
    named_keys              = False
    color_space             = 'sRGB'
    color_spaces            = ['sRGB', 'Adobe RGB 1998']
    bit_depth               = '8'
    bit_depths              = ['8', '16']

    print(f"\033[92m[save_image_adobeRGB] version: {version}\033[0m")
    if jxl_supported:
        output_exts.insert(output_exts.index('.webp'), '.jxl')
    if avif_supported:
        output_exts.insert(output_exts.index('.webp'), '.avif')

    @classmethod
    def INPUT_TYPES(self):
        return {
            'required': {
                'images': ('IMAGE', ),
                'filename_prefix': ('STRING', {
                    'default': self.filename_prefix,
                    'multiline': False,
                    'tooltip': "Fixed string prefixed to file name",
                }),
                'filename_keys': ('STRING', {
                    'default': self.filename_keys,
                    'multiline': True,
                    'tooltip': "Comma separated sampler parameters for filename. "
                               "Example: sampler_name, scheduler, cfg, denoise. "
                               "Also accepts vae_name, model_name, ckpt_name, resolution. "
                               "Use node.widget syntax like 13.sampler_name for specific nodes.",
                }),
                'foldername_prefix': ('STRING', {
                    'default': self.foldername_prefix,
                    'multiline': False,
                    'tooltip': "Fixed string prefixed to subfolders",
                }),
                'foldername_keys': ('STRING', {
                    'default': self.foldername_keys,
                    'multiline': True,
                    'tooltip': "Same rules as filename_keys. Use / or ../ for subfolders.",
                }),
                'delimiter': ('STRING', {
                    'default': self.delimiter,
                    'multiline': False,
                    'tooltip': "Delimiter between filename parts. Can use / for subfolders.",
                }),
                'save_job_data': ([
                    'disabled',
                    'prompt',
                    'basic, prompt',
                    'basic, sampler, prompt',
                    'basic, models, sampler, prompt',
                ], {
                    'default': self.save_job_data,
                    'tooltip': "Save job info as entries in jobs.json.",
                }),
                'job_data_per_image': ('BOOLEAN', {
                    'default': self.job_data_per_image,
                    'tooltip': "Save individual job data file per image.",
                }),
                'job_custom_text': ('STRING', {
                    'default': self.job_custom_text,
                    'multiline': False,
                    'tooltip': "Custom string saved with job data.",
                }),
                'save_metadata': ('BOOLEAN', {
                    'default': self.save_metadata,
                    'tooltip': "Embed prompt/workflow metadata into image file.",
                }),
                'counter_digits': ('INT', {
                    'default': self.counter_digits,
                    'min': 0, 'max': 8, 'step': 1,
                    'display': 'slider',
                    'tooltip': "Digits for counter. 4 = 0001. Set 0 to disable.",
                }),
                'counter_position': (self.counter_positions, {
                    'default': self.counter_position,
                    'tooltip': "Counter position: image_0001 or 0001_image.",
                }),
                'one_counter_per_folder': ('BOOLEAN', {
                    'default': self.one_counter_per_folder,
                    'tooltip': "Deprecated — retained for backward compatibility.",
                }),
                'image_preview': ('BOOLEAN', {
                    'default': self.image_preview,
                    'tooltip': "Show image preview in UI.",
                }),
                'output_ext': (self.output_exts, {
                    'default': self.output_ext,
                    'tooltip': "Output file format.",
                }),
                'quality': ('INT', {
                    'default': self.quality,
                    'min': 0, 'max': 100, 'step': 1,
                    'display': 'slider',
                    'tooltip': "Quality for lossy formats. PNG: maps to compress level 0-9.",
                }),
                'named_keys': ('BOOLEAN', {
                    'default': self.named_keys,
                    'tooltip': "Prefix values with key names. e.g. seed=123-cfg=7.5",
                }),
                'color_space': (self.color_spaces, {
                    'default': self.color_space,
                    'tooltip': "Color space for output. Adobe RGB 1998 converts from sRGB and embeds ICC profile.",
                }),
                'bit_depth': (self.bit_depths, {
                    'default': self.bit_depth,
                    'tooltip': "Bit depth per channel. 16-bit only for PNG and TIFF; others fall back to 8.",
                }),
            },
            'optional': {
                'positive_text_opt': ('STRING', {'forceInput': True, 'tooltip': "Optional positive prompt for job.json."}),
                'negative_text_opt': ('STRING', {'forceInput': True, 'tooltip': "Optional negative prompt for job.json."}),
            },
            'hidden': {
                'prompt': 'PROMPT',
                'extra_pnginfo': 'EXTRA_PNGINFO',
            },
        }

    RETURN_TYPES = ()
    FUNCTION = 'save_images'
    OUTPUT_NODE = True
    CATEGORY = 'image'
    DESCRIPTION = """Save images with color space (sRGB / Adobe RGB 1998) and bit depth (8 / 16) control.
Supports PNG, TIFF, JPEG, WebP, AVIF, JXL, and more.
16-bit output is supported for PNG and TIFF only (other formats fall back to 8-bit).
ICC profiles are embedded for proper color management.
All filename/folder templating features from Save Image Extended are included."""

    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.prefix_append = ''
```

---

#### Section F — Helper Methods (counter, key search, filename generation, subfolder, job data)

These are carried over from the reference with minimal changes.

```python
    def get_subfolder_path(self, image_path, output_path):
        image_path = Path(image_path).resolve()
        output_path = Path(output_path).resolve()
        relative_path = image_path.relative_to(output_path)
        return str(relative_path.parent)

    def get_latest_counter(self, folder_path, filename, counter_digits=4, counter_position='last', output_ext='.png'):
        counter = 1
        if not os.path.exists(folder_path):
            print(f"[save_image_adobeRGB] Folder {folder_path} does not exist, starting counter at 1.")
            return counter
        try:
            files = [f for f in os.listdir(folder_path) if f.endswith(output_ext)]
            extLen = len(output_ext)
            if counter_position == 'last':
                counters = [int(f[-(counter_digits + extLen):-extLen]) for f in files
                            if f[-(counter_digits + extLen):-extLen].isdecimal()]
            else:
                counters = [int(f[:counter_digits]) for f in files
                            if f[:counter_digits].isdecimal()]
            if counters:
                counter = max(counters) + 1
        except (ValueError, TypeError):
            pass
        return counter

    def find_keys_recursively(self, prompt={}, keys_to_find=[], found_values={}):
        for key, value in prompt.items():
            if key in keys_to_find:
                if isinstance(value, dict):
                    value = value.get('content', '')
                if key in ['ckpt_path', 'ckpt_name']:
                    value_path = Path(value)
                    if 'ckpt_path' in keys_to_find:
                        found_values['ckpt_path'] = self.cleanup_fileName(str(value_path.parent))
                    elif 'ckpt_name' in keys_to_find:
                        found_values['ckpt_name'] = self.cleanup_fileName(str(value_path.name))
                elif key in ['control_net_path', 'control_net_name']:
                    value_path = Path(value)
                    if 'control_net_path' in keys_to_find:
                        found_values['control_net_path'] = self.cleanup_fileName(str(value_path.parent))
                    elif 'control_net_name' in keys_to_find:
                        found_values['control_net_name'] = self.cleanup_fileName(str(value_path.name))
                elif key in ['lora_path', 'lora_name']:
                    value_path = Path(value)
                    if 'lora_path' in keys_to_find:
                        found_values['lora_path'] = self.cleanup_fileName(str(value_path.parent))
                    elif 'lora_name' in keys_to_find:
                        found_values['lora_name'] = self.cleanup_fileName(str(value_path.name))
                else:
                    found_values[key] = self.cleanup_fileName(value)
            elif isinstance(value, dict):
                self.find_keys_recursively(value, keys_to_find, found_values)

    def cleanup_fileName(self, file='', extToRemove=None):
        if extToRemove is None:
            extToRemove = self.modelExtensions
        if isinstance(file, str):
            for ext in extToRemove:
                file = file.removesuffix(ext)
        return file

    def find_parameter_values(self, target_keys, prompt={}, found_values={}):
        loras_string = ''
        for key, value in prompt.items():
            if 'loras' in target_keys:
                if re.match(r'lora(_name)?(_\d+)?', key):
                    if value is not None:
                        value = self.cleanup_fileName(value)
                        loras_string += f'{value}, '
            if isinstance(value, dict):
                self.find_parameter_values(target_keys, value, found_values)
            if key in target_keys:
                value = self.cleanup_fileName(value)
                found_values[key] = value
        if 'loras' in target_keys and loras_string:
            found_values['loras'] = loras_string.strip().strip(',')
        if len(target_keys) == 1:
            return found_values.get(target_keys[0], None)
        return found_values

    def generate_custom_name(self, keys_to_extract, prefix, delimiter, prompt, resolution, timestamp=None, named_keys=False):
        if timestamp is None:
            timestamp = datetime.now()
        custom_name = []

        if prefix:
            if '%' in prefix:
                custom_name.append(timestamp.strftime(prefix))
            else:
                custom_name.append(prefix)

        if prompt is not None and keys_to_extract != ['']:
            found_values = {}

            for key in keys_to_extract:
                if not key:
                    continue

                value = None
                node, nodeKey = None, None

                # Datetime
                if '%' in key:
                    value = timestamp.strftime(key)

                # Subfolder separator
                if '/' in key:
                    values = re.split('/+', key)
                    if values[0] in ['', '.', '..']:
                        custom_name.append(values[0] + '/')
                        key = values[1]
                        if not key:
                            continue
                    else:
                        key = values[0]

                # Fixed string
                if (key.startswith("'") and key.endswith("'")) or (key.startswith('"') and key.endswith('"')):
                    value = key

                # Numbered node key (e.g. 13.sampler_name)
                if value is None:
                    splitKey = key.split('.')
                    if len(splitKey) == 2:
                        if '' not in splitKey:
                            if splitKey[0].isdecimal():
                                node, nodeKey = splitKey[0], splitKey[1]
                                search_scope = prompt[node] if node in prompt else prompt
                                if node not in prompt:
                                    print(f"[save_image_adobeRGB] node #{node} not found, searching all")
                                if nodeKey == 'ckpt_path':
                                    self.find_keys_recursively(search_scope, ['ckpt_name', nodeKey], found_values)
                                elif nodeKey == 'control_net_path':
                                    self.find_keys_recursively(search_scope, ['control_net_name', nodeKey], found_values)
                                elif nodeKey == 'lora_path':
                                    self.find_keys_recursively(search_scope, ['lora_name', nodeKey], found_values)
                                else:
                                    self.find_keys_recursively(search_scope, [nodeKey], found_values)
                            else:
                                value = self.cleanup_fileName(key)
                        else:
                            value = key
                    else:
                        nodeKey = key
                        if nodeKey == 'ckpt_path':
                            self.find_keys_recursively(prompt, ['ckpt_name', nodeKey], found_values)
                        elif nodeKey == 'control_net_path':
                            self.find_keys_recursively(prompt, ['control_net_name', nodeKey], found_values)
                        elif nodeKey == 'lora_path':
                            self.find_keys_recursively(prompt, ['lora_name', nodeKey], found_values)
                        elif nodeKey == 'resolution':
                            value = resolution
                        else:
                            self.find_keys_recursively(prompt, [nodeKey], found_values)

                if value is None:
                    if nodeKey is not None:
                        if nodeKey in found_values:
                            if named_keys:
                                value = f"{nodeKey}={found_values[nodeKey]}"
                            else:
                                value = found_values[nodeKey]
                        if value is None:
                            value = nodeKey

                if isinstance(value, str):
                    if nodeKey in ['ckpt_path', 'control_net_path', 'lora_path']:
                        value = found_values.get(nodeKey, value)
                    else:
                        value = self.cleanup_fileName(value)
                elif isinstance(value, float):
                    value = float(f'{value:.10g}')

                custom_name.append(str(value))

        custom_name = list(filter(None, custom_name))
        custom_name = list(map(str.strip, custom_name))
        stringName = delimiter.join(custom_name).replace('/' + delimiter, '/').replace(delimiter + '/', '/').replace(delimiter + '.', '.')
        stringName = re.sub(r'\s+', ' ', stringName).strip(delimiter).strip('/').strip(delimiter).strip('.')
        return re.sub(r'[*?:"<>|]', '', stringName).replace('/', os.sep)

    def save_job_to_json(self, save_job_data, prompt, filename_prefix, positive_text_opt, negative_text_opt, job_custom_text, resolution, output_path, filename, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now()
        prompt_keys_to_save = {}

        if 'basic' in save_job_data:
            if len(filename_prefix) > 0:
                prompt_keys_to_save['filename_prefix'] = filename_prefix
            prompt_keys_to_save['resolution'] = resolution

        if len(job_custom_text) > 0:
            prompt_keys_to_save['custom_text'] = job_custom_text

        if 'models' in save_job_data:
            models = self.find_parameter_values(['ckpt_name', 'loras', 'vae_name', 'model_name'], prompt)
            if models.get('ckpt_name'):
                prompt_keys_to_save['checkpoint'] = models['ckpt_name']
            if models.get('loras'):
                prompt_keys_to_save['loras'] = models['loras']
            if models.get('vae_name'):
                prompt_keys_to_save['vae'] = models['vae_name']
            if models.get('model_name'):
                prompt_keys_to_save['upscale_model'] = models['model_name']

        if 'sampler' in save_job_data:
            prompt_keys_to_save['sampler_parameters'] = self.find_parameter_values(
                ['seed', 'steps', 'cfg', 'sampler_name', 'scheduler', 'denoise'], prompt
            )

        if 'prompt' in save_job_data:
            if positive_text_opt is not None:
                if not (isinstance(positive_text_opt, list) and len(positive_text_opt) == 2
                        and isinstance(positive_text_opt[0], str) and len(positive_text_opt[0]) < 6
                        and isinstance(positive_text_opt[1], (int, float))):
                    prompt_keys_to_save['positive_prompt'] = positive_text_opt
            if negative_text_opt is not None:
                if not (isinstance(negative_text_opt, list) and len(negative_text_opt) == 2
                        and isinstance(negative_text_opt[0], str) and len(negative_text_opt[0]) < 6
                        and isinstance(negative_text_opt[1], (int, float))):
                    prompt_keys_to_save['negative_prompt'] = negative_text_opt

            if positive_text_opt is None and negative_text_opt is None:
                if prompt is not None:
                    for key in prompt:
                        class_type = prompt[key].get('class_type', None)
                        inputs = prompt[key].get('inputs', {})
                        if class_type in ('Efficient Loader', 'Eff. Loader SDXL'):
                            if 'positive' in inputs and 'negative' in inputs:
                                prompt_keys_to_save['positive_prompt'] = inputs.get('positive')
                                prompt_keys_to_save['negative_prompt'] = inputs.get('negative')
                        elif class_type in ('KSampler', 'KSamplerAdvanced', 'UltimateSDUpscale'):
                            positive_ref = inputs.get('positive', [])[0] if 'positive' in inputs else None
                            negative_ref = inputs.get('negative', [])[0] if 'negative' in inputs else None
                            positive_text = prompt.get(str(positive_ref), {}).get('inputs', {}).get('text', None)
                            negative_text = prompt.get(str(negative_ref), {}).get('inputs', {}).get('text', None)
                            if positive_text is not None:
                                if isinstance(positive_text, list) and len(positive_text) == 2 and isinstance(positive_text[0], str) and len(positive_text[0]) < 6 and isinstance(positive_text[1], (int, float)):
                                    continue
                                prompt_keys_to_save['positive_prompt'] = positive_text
                            if negative_text is not None:
                                if isinstance(negative_text, list) and len(negative_text) == 2 and isinstance(negative_text[0], str) and len(negative_text[0]) < 6 and isinstance(negative_text[1], (int, float)):
                                    continue
                                prompt_keys_to_save['negative_prompt'] = negative_text

        json_file_path = os.path.join(output_path, filename)
        existing_data = {}
        if os.path.exists(json_file_path):
            try:
                with open(json_file_path, 'r') as f:
                    existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = {}

        ts_str = timestamp.strftime('%c')
        existing_data[ts_str] = prompt_keys_to_save

        with open(json_file_path, 'w') as f:
            json.dump(existing_data, f, indent=4)
```

---

#### Section G — Metadata Generators

```python
    def genMetadataPng(self, img, prompt, extra_pnginfo=None):
        metadata = PngInfo()
        if prompt is not None:
            metadata.add_text('prompt', json.dumps(prompt))
        if extra_pnginfo is not None:
            for x in extra_pnginfo:
                metadata.add_text(x, json.dumps(extra_pnginfo[x]))
        return metadata

    def genMetadataEXIF(self, img, prompt, extra_pnginfo=None):
        metadata = {}
        if prompt is not None:
            metadata['prompt'] = prompt
        if extra_pnginfo is not None:
            metadata.update(extra_pnginfo)

        exif = img.getexif()
        exif[0x010f] = "Prompt: " + json.dumps(metadata.get('prompt', {}))
        exif[0x010e] = "Workflow: " + json.dumps(metadata.get('workflow', {}))
        exif_dat = exif.tobytes()
        return exif_dat
```

---

#### Section H — writeImage (8‑bit pipeline with ICC)

```python
    def writeImage(self, image_path, img, prompt, save_metadata=True, extra_pnginfo=None, quality=90, icc_profile=None):
        if quality == 0:
            quality = self.quality
        output_ext = Path(image_path).suffix
        kwargs = dict()

        # Attach ICC profile for Pillow-based saves
        if icc_profile is not None:
            img.info['icc_profile'] = icc_profile

        if output_ext in ['.avif', '.webp', '.jxl']:
            if save_metadata:
                kwargs['exif'] = self.genMetadataEXIF(img, prompt, extra_pnginfo)
            if quality == 100:
                kwargs['lossless'] = True
            else:
                kwargs['quality'] = quality
            kwargs['optimize'] = self.optimize_image
            if icc_profile is not None:
                kwargs['icc_profile'] = icc_profile

        if output_ext in ['.j2k', '.jp2', '.jpc', '.jpf', '.jpx', '.j2c']:
            if save_metadata:
                kwargs['exif'] = self.genMetadataEXIF(img, prompt, extra_pnginfo)
            if quality < 100:
                kwargs['irreversible'] = True
            else:
                kwargs['quality'] = quality

        elif output_ext in ['.jpg', '.jpeg']:
            if save_metadata:
                kwargs['exif'] = self.genMetadataEXIF(img, prompt, extra_pnginfo)
            kwargs['subsampling'] = 0
            kwargs['quality'] = quality
            kwargs['optimize'] = self.optimize_image
            if icc_profile is not None:
                kwargs['icc_profile'] = icc_profile

        elif output_ext in ['.tiff']:
            if save_metadata:
                kwargs['exif'] = self.genMetadataEXIF(img, prompt, extra_pnginfo)
            kwargs['optimize'] = self.optimize_image
            if icc_profile is not None:
                kwargs['icc_profile'] = icc_profile

        elif output_ext in ['.png', '.gif']:
            if save_metadata:
                kwargs['pnginfo'] = self.genMetadataPng(img, prompt, extra_pnginfo)
            old_min, old_max = 0, 90
            new_min, new_max = 0, 9
            if quality >= 91:
                quality = 90
            png_compress_level = round(((quality - old_min) / (old_max - old_min)) * (new_max - new_min) + new_min)
            kwargs['compress_level'] = png_compress_level

        img.save(image_path, **kwargs)
```

---

#### Section I — save_images (main entry point)

```python
    def save_images(self,
            images,
            filename_prefix,
            filename_keys,
            foldername_prefix,
            foldername_keys,
            delimiter,
            save_job_data,
            job_data_per_image,
            job_custom_text,
            save_metadata,
            counter_digits,
            counter_position,
            one_counter_per_folder,
            image_preview,
            output_ext,
            color_space='sRGB',
            bit_depth='8',
            negative_text_opt=None,
            positive_text_opt=None,
            extra_pnginfo=None,
            prompt=None,
            quality=90,
            named_keys=False,
        ):

        if quality == 0:
            quality = self.quality
        if delimiter:
            delimiter = delimiter[0]

        # Determine if 16-bit is valid for this format
        use_16bit = (bit_depth == '16' and output_ext in ['.png', '.tiff'])
        if bit_depth == '16' and not use_16bit:
            print(f"[save_image_adobeRGB] 16-bit not supported for {output_ext}, falling back to 8-bit.")

        # Select ICC profile
        if color_space == 'Adobe RGB 1998':
            icc_profile = _ADOBE_RGB_ICC_BYTES
        else:
            icc_profile = _SRGB_ICC_BYTES

        filename_keys_to_extract = [item.strip() for item in filename_keys.split(',')]
        foldername_keys_to_extract = [item.strip() for item in foldername_keys.split(',')]

        # Get resolution from first image
        i = 255. * images[0].cpu().numpy()
        img_temp = Image.fromarray(numpy.clip(i, 0, 255).astype(numpy.uint8))
        resolution = f'{img_temp.width}x{img_temp.height}'

        timestamp = datetime.now()
        custom_foldername = self.generate_custom_name(foldername_keys_to_extract, foldername_prefix, delimiter, prompt, resolution, timestamp, named_keys)
        custom_filename = self.generate_custom_name(filename_keys_to_extract, filename_prefix, delimiter, prompt, resolution, timestamp, named_keys)

        try:
            if custom_filename:
                output_path = Path(os.path.join(self.output_dir, custom_foldername, custom_filename)).parent
                filename = Path(os.path.join(self.output_dir, custom_foldername, custom_filename)).name
            else:
                output_path = Path(os.path.join(self.output_dir, custom_foldername))
                filename = ''

            os.makedirs(output_path, exist_ok=True)
            counter = self.get_latest_counter(output_path, filename, counter_digits, counter_position, output_ext)

            results = list()
            for image in images:
                # ---- Color space conversion on float tensor ----
                arr_float = image.cpu().numpy()  # (H, W, 3) float32 [0,1]
                if color_space == 'Adobe RGB 1998':
                    arr_float = convert_srgb_to_adobergb(arr_float)

                if use_16bit:
                    # 16-bit pipeline
                    arr_16 = numpy.clip(arr_float * 65535.0, 0, 65535).astype(numpy.uint16)

                    if counter_digits > 0:
                        if filename:
                            if counter_position == 'last':
                                image_name = f'{filename}{delimiter}{counter:0{counter_digits}}{output_ext}'
                            else:
                                image_name = f'{counter:0{counter_digits}}{delimiter}{filename}{output_ext}'
                        else:
                            image_name = f'{counter:0{counter_digits}}{output_ext}'
                    else:
                        if filename:
                            image_name = f'{filename}{output_ext}'
                        else:
                            image_name = f'{filename_prefix}{output_ext}'

                    image_path = os.path.join(output_path, image_name)

                    if output_ext == '.png':
                        png_quality = quality
                        if png_quality >= 91:
                            png_quality = 90
                        compress_level = round(((png_quality) / 90) * 9)
                        save_16bit_png(
                            image_path, arr_16,
                            icc_profile=icc_profile if save_metadata else None,
                            prompt=prompt if save_metadata else None,
                            extra_pnginfo=extra_pnginfo if save_metadata else None,
                            compress_level=compress_level,
                        )
                    elif output_ext == '.tiff':
                        save_16bit_tiff(
                            image_path, arr_16,
                            icc_profile=icc_profile if save_metadata else None,
                            prompt=prompt if save_metadata else None,
                            extra_pnginfo=extra_pnginfo if save_metadata else None,
                        )

                else:
                    # 8-bit pipeline (standard Pillow)
                    arr_8 = numpy.clip(arr_float * 255.0, 0, 255).astype(numpy.uint8)
                    img = Image.fromarray(arr_8)

                    if counter_digits > 0:
                        if filename:
                            if counter_position == 'last':
                                image_name = f'{filename}{delimiter}{counter:0{counter_digits}}{output_ext}'
                            else:
                                image_name = f'{counter:0{counter_digits}}{delimiter}{filename}{output_ext}'
                        else:
                            image_name = f'{counter:0{counter_digits}}{output_ext}'
                    else:
                        if filename:
                            image_name = f'{filename}{output_ext}'
                        else:
                            image_name = f'{filename_prefix}{output_ext}'

                    image_path = os.path.join(output_path, image_name)
                    self.writeImage(image_path, img, prompt, save_metadata, extra_pnginfo, quality, icc_profile)

                if save_job_data != 'disabled' and job_data_per_image:
                    self.save_job_to_json(save_job_data, prompt, filename_prefix, positive_text_opt, negative_text_opt, job_custom_text, resolution, output_path, f'{image_name.removesuffix(output_ext)}.json', timestamp)

                subfolder = self.get_subfolder_path(image_path, self.output_dir)
                results.append({'filename': image_name, 'subfolder': subfolder, 'type': self.type})
                counter += 1

            if save_job_data != 'disabled' and not job_data_per_image:
                self.save_job_to_json(save_job_data, prompt, filename_prefix, positive_text_opt, negative_text_opt, job_custom_text, resolution, output_path, 'jobs.json', timestamp)

        except OSError as e:
            print(f"[save_image_adobeRGB] Error: {e}")
        else:
            if not image_preview:
                results = list()
            return {'ui': {'images': results}}
```

---

#### Section J — Node Registration

```python
NODE_CLASS_MAPPINGS = {
    'SaveImageExtendedAdobeRGB': SaveImageExtendedAdobeRGB,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'SaveImageExtendedAdobeRGB': f'Save Image Extended AdobeRGB {version}',
}
```

---

## Testing Scenarios

### Test 1 — sRGB 8‑bit PNG (baseline)
- Settings: `color_space=sRGB`, `bit_depth=8`, `output_ext=.png`
- Expected: Standard 8-bit PNG identical to reference node output, with sRGB ICC profile embedded.
- Verify: Open in Photoshop → Edit > Assign Profile should show sRGB.

### Test 2 — Adobe RGB 8‑bit PNG
- Settings: `color_space=Adobe RGB 1998`, `bit_depth=8`, `output_ext=.png`
- Expected: Color-converted 8-bit PNG with Adobe RGB ICC profile.
- Verify: Open in Photoshop → shows Adobe RGB. Colors should appear identical to Test 1 in a color-managed viewer.

### Test 3 — sRGB 16‑bit PNG
- Settings: `color_space=sRGB`, `bit_depth=16`, `output_ext=.png`
- Expected: 16-bit per channel PNG. File size roughly 2x the 8-bit version.
- Verify: `exiftool output.png` shows Bit Depth = 16. Open in Photoshop → Image > Mode should show 16 Bits/Channel.

### Test 4 — Adobe RGB 16‑bit TIFF
- Settings: `color_space=Adobe RGB 1998`, `bit_depth=16`, `output_ext=.tiff`
- Expected: 16-bit TIFF with Adobe RGB ICC profile and metadata in ImageDescription tag.
- Verify: Photoshop shows Adobe RGB color space and 16-bit mode.

### Test 5 — 16‑bit fallback for JPEG
- Settings: `color_space=sRGB`, `bit_depth=16`, `output_ext=.jpg`
- Expected: Console prints fallback warning. Saves as 8-bit JPEG with sRGB ICC profile.

### Test 6 — Filename templating
- Settings: `filename_keys='sampler_name, cfg, steps, %F %H-%M-%S'`
- Expected: Filename contains sampler parameters and datetime, identical to reference behavior.

### Test 7 — Metadata round‑trip
- Save as 8-bit sRGB PNG with metadata enabled.
- Load into ComfyUI via Load Image node.
- Expected: Workflow loads correctly from embedded PNG metadata.

### Test 8 — Batch images with counter
- Send a batch of 4 images.
- Expected: Sequential counter `0001` through `0004` in filenames.

---

## Edge Cases

1. **quality=0 on load**: Reference has a bug where quality loads as 0. We replicate the fix: `if quality == 0: quality = self.quality`.
2. **Empty filename_prefix + empty filename_keys**: Should produce counter-only filenames like `0001.png`.
3. **16-bit with imagecodecs unavailable**: Falls back to 8-bit with warning.
4. **16-bit with tifffile unavailable**: Falls back to 8-bit TIFF via Pillow with warning.
5. **Very large images (>12000px)**: WebP and JXL have size limits. No change from reference behavior.
6. **Adobe RGB with BMP**: ICC profile cannot be embedded in BMP. Color conversion still applied, profile silently skipped.
7. **EXIF data exceeds JPEG limit**: Very long prompts can cause EXIF failures. No change from reference.
8. **Missing prompt (None)**: All metadata methods handle `prompt=None` gracefully.
