# True Adobe RGB (1998) — Implementation Plan

Assessment of `save_image_extended_adobeRGB.py` against `True-adobeRGB-checklist.md`.
All line references are to `save_image_extended_adobeRGB.py`.

---

## Assessment Summary

| Checklist Section | Status | Issues |
|---|---|---|
| 1. Color Space Conversion | PASS | Quantization rounding fixed |
| 2. ICC Profile Construction | PASS | All header/tag/structure issues fixed |
| 3. TIFF Encoder (ICC embed) | PASS | Uses `tifffile` — handles tag 34675 correctly |
| 4. TIFF Structure | PASS | Handled by `tifffile` library |
| 5. Validation | PENDING | Manual tests not yet run |

---

## Issues Found

### ISSUE 1 — ICC Header: Wrong CMM Type
**Severity**: Medium
**File**: `save_image_extended_adobeRGB.py` **line 219**
**Current**: `b'lcms'`
**Required**: `b'ADBE'`
**Why**: The Adobe RGB (1998) profile was created by Adobe. Photoshop and color-managed apps compare this field when identifying known profiles. Using `lcms` makes the profile appear as a generic Little CMS output rather than a recognized Adobe profile.

- [x] Change CMM type from `b'lcms'` to `b'ADBE'`

---

### ISSUE 2 — ICC Header: Wrong Creation Date
**Severity**: Medium
**File**: `save_image_extended_adobeRGB.py` **line 224-225**
**Current**: `2025, 1, 1, 0, 0, 0`
**Required**: `1999, 6, 3, 0, 0, 0`
**Why**: The canonical Adobe RGB (1998) profile uses creation date `1999-06-03`. Profile-matching logic in some applications compares header bytes (including date) to identify known profiles. A different date causes the profile to be treated as unknown/custom.

- [x] Change creation date to `1999, 6, 3, 0, 0, 0`

---

### ISSUE 3 — ICC Header: Wrong Platform
**Severity**: Low
**File**: `save_image_extended_adobeRGB.py` **line 227**
**Current**: `b'MSFT'`
**Required**: `b'APPL'`
**Why**: Adobe's published profile uses `APPL` (Apple) as the primary platform. This is a convention from the original profile, not a platform restriction. Using `MSFT` makes the profile non-matching against reference copies.

- [x] Change platform from `b'MSFT'` to `b'APPL'`

---

### ISSUE 4 — ICC Header: Missing Creator Signature
**Severity**: Low
**File**: `save_image_extended_adobeRGB.py` **line 237**
**Current**: `b'\x00' * 4` (empty)
**Required**: `b'ADBE'`
**Why**: Identifies who created the profile. The canonical profile uses `ADBE`.

- [x] Change creator field from `b'\x00' * 4` to `b'ADBE'`

---

### ISSUE 5 — ICC Primary XYZ: Truncated Precision
**Severity**: High
**File**: `save_image_extended_adobeRGB.py` **lines 146-148**
**Current** (5 decimal places):
```python
rX, rY, rZ = 0.60974, 0.31111, 0.01947
gX, gY, gZ = 0.20528, 0.62567, 0.06087
bX, bY, bZ = 0.14919, 0.06322, 0.74457
```
**Required** (7 decimal places, matching checklist):
```python
rX, rY, rZ = 0.6097559, 0.3111145, 0.0194702
gX, gY, gZ = 0.2052401, 0.6256714, 0.0608902
bX, bY, bZ = 0.1492240, 0.0632141, 0.7445396
```
**Why**: These values are encoded as s15Fixed16 (1/65536 precision ~ 0.0000153). Truncating to 5 decimals introduces up to 1 LSB error per primary. This shifts the encoded chromaticity and causes the profile to not byte-match the canonical Adobe profile. Color-managed applications that fingerprint ICC profiles by content will fail to recognize it.

- [x] Update all 9 primary XYZ values to 7-decimal precision

---

### ISSUE 6 — ICC White Point: Precision Alignment
**Severity**: Low
**File**: `save_image_extended_adobeRGB.py` **line 150**
**Current**: `wX, wY, wZ = 0.95045, 1.00000, 1.08905`
**Checklist reference**: `(0.9505, 1.0, 1.0890)` — D65
**Analysis**: The values are functionally equivalent (difference < 1 LSB in s15Fixed16). Current values are actually *more* precise. No change needed, but documenting for clarity.

- [x] White point values are acceptable (no change needed)

---

### ISSUE 7 — ICC TRC Tags: Not Sharing Offsets
**Severity**: Medium
**File**: `save_image_extended_adobeRGB.py` **lines 160, 202-213**
**Current**: Three separate `curv` tag data blocks are built and stored at three different offsets.
**Required**: `gTRC` and `bTRC` should point to the same offset as `rTRC` (all three curves are identical).
**Why**: The canonical Adobe RGB profile shares a single TRC data block across all three channels. This reduces profile size and is the expected structure. Profile comparison tools (and some color engines) may reject or flag a profile with redundant identical TRC data at different offsets.

- [x] Build `tag_TRC` data once, then point all three tag table entries (`rTRC`, `gTRC`, `bTRC`) to the same offset

---

### ISSUE 8 — ICC `desc` Tag: Incomplete Structure
**Severity**: Medium
**File**: `save_image_extended_adobeRGB.py` **lines 162-175**
**Current**: ASCII string + 8 zero bytes (Unicode lang code + count). Missing ScriptCode section entirely.
**Required (ICC v2.1 `desc` type):**
```
4 bytes  — type signature 'desc'
4 bytes  — reserved (zeros)
4 bytes  — ASCII description count (including null terminator)
N bytes  — ASCII description string + null
4 bytes  — Unicode language code
4 bytes  — Unicode description count
M bytes  — Unicode description (2 * count bytes, 0 if count is 0)
2 bytes  — ScriptCode code
1 byte   — ScriptCode description count
67 bytes — ScriptCode description string (fixed 67 bytes, zero-padded)
```
**Why**: Some ICC validators and older applications expect the full `desc` tag structure. The missing ScriptCode section (70 bytes) may cause parsers to read past the tag boundary or reject the profile.

- [x] Add ScriptCode section: `b'\x00' * 2` (code) + `b'\x00'` (count) + `b'\x00' * 67` (fixed string) after the Unicode section

---

### ISSUE 9 — Quantization: Truncation Instead of Rounding
**Severity**: Low
**File**: `save_image_extended_adobeRGB.py` **line 1002**
**Current**:
```python
arr_16 = numpy.clip(arr_float * 65535.0, 0, 65535).astype(numpy.uint16)
```
**Required**:
```python
arr_16 = numpy.clip(numpy.round(arr_float * 65535.0), 0, 65535).astype(numpy.uint16)
```
**Why**: `.astype(uint16)` truncates (floors) the fractional part. A value of `32767.9` becomes `32767` instead of `32768`. This introduces a systematic -0.5 LSB bias across all pixels. Adding `numpy.round()` before casting eliminates this bias.

- [x] Add `numpy.round()` before `.astype(numpy.uint16)` on line 1002

---

### BONUS — ICC Tag Table: Sort Order
**Severity**: Medium
**Discovered during implementation** — not in original assessment.
**Why**: ICC spec (ICC.1:2004-10, section 7.3) requires tag table entries sorted ascending by 4-byte signature. The original order was unsorted.

- [x] Tag entries reordered: `bTRC < bXYZ < cprt < desc < gTRC < gXYZ < rTRC < rXYZ < wtpt`

---

## Implementation Sequence

Apply fixes in this order (each change is independent and safe):

### Phase 1 — ICC Profile Corrections (Issues 1-5, 7-8, bonus) -- COMPLETE

All changes are within `_build_adobe_rgb_icc()`.

```
Step 1:  Fix primary XYZ precision           (Issue 5)  ......... DONE
Step 2:  Fix ICC header CMM type             (Issue 1)  ......... DONE
Step 3:  Fix ICC header creation date        (Issue 2)  ......... DONE
Step 4:  Fix ICC header platform             (Issue 3)  ......... DONE
Step 5:  Fix ICC header creator              (Issue 4)  ......... DONE
Step 6:  Share TRC tag offsets               (Issue 7)  ......... DONE
Step 7:  Complete desc tag structure          (Issue 8)  ......... DONE
Step 7b: Sort tag table entries              (Bonus)    ......... DONE
```

### Phase 2 — Pixel Pipeline Fix (Issue 9) -- COMPLETE

```
Step 8:  Add numpy.round() to 16-bit quantization (Issue 9) ... DONE
```

### Phase 3 — Validation (Checklist Section 5) -- PENDING

```
Step 9:  Export a test TIFF (16-bit, Adobe RGB)
Step 10: Run exiftool / tiffinfo — verify ICC profile description = "Adobe RGB (1998)"
Step 11: Open in Photoshop — verify color profile detected
Step 12: Open in GIMP — verify ICC prompt on import
Step 13: Visual comparison — Adobe RGB should appear slightly desaturated in unmanaged viewer
Step 14: Round-trip test — export -> reimport -> convert to sRGB -> compare
```

### Build Verification -- COMPLETE

```
- [x] Python syntax check passes
- [x] ICC profile builds without assertion errors
- [x] Profile size: 468 bytes (header + tag table + tag data consistent)
- [x] Tag table sorted ascending by signature
- [x] Profile description reads "Adobe RGB (1998)"
- [x] TRC gamma = 2.19921875 (0x0233)
```

---

## What Is Already Correct

These items from the checklist are properly implemented and needed no changes:

| Checklist Item | Location | Status |
|---|---|---|
| sRGB linearization (piecewise, gamma 2.4) | `srgb_to_linear()` | PASS |
| Matrix multiply (sRGB linear -> Adobe RGB linear) | `_M_SRGB_TO_ADOBE_LINEAR` | PASS |
| Clamp after matrix multiply | `convert_srgb_to_adobergb()` | PASS |
| Adobe RGB gamma = 563/256 (exact) | `_ADOBE_GAMMA` | PASS |
| Inverse gamma application | `linear_to_adobe_gamma()` | PASS |
| ICC version 2.1.0 | Header | PASS |
| ICC device class `mntr` | Header | PASS |
| ICC color space `RGB ` | Header | PASS |
| ICC PCS `XYZ ` | Header | PASS |
| ICC PCS illuminant D50 | Header | PASS |
| ICC profile signature `acsp` | Header | PASS |
| s15Fixed16 encoding function | `_build_icc_s15fixed16()` | PASS |
| Big-endian ICC fields | All `struct.pack('>...')` | PASS |
| 4-byte aligned tag data | Padding in tag builders | PASS |
| Profile cached at module level | `_ADOBE_RGB_ICC_BYTES` | PASS |
| TIFF tag 34675 for ICC embed | `save_16bit_tiff()` | PASS |
| TIFF via tifffile (handles structure) | `tifffile.imwrite()` | PASS |
| 16-bit TIFF pixel data (uint16) | quantization line | PASS |
| Color space dropdown in node UI | `color_spaces` | PASS |
| Bit depth dropdown in node UI | `bit_depths` | PASS |
| Conversion only when Adobe RGB selected | `save_images()` | PASS |
| ICC profile selection by color space | `save_images()` | PASS |

---

## Risk Assessment

- **All Phase 1 changes** are confined to `_build_adobe_rgb_icc()` and only affect the cached ICC profile bytes. They cannot break pixel data or TIFF structure.
- **Phase 2** is a single-line change with no side effects.
- **Phase 3** is read-only validation.

No changes affect the 8-bit pipeline, sRGB pipeline, filename generation, metadata handling, or any other node functionality.
