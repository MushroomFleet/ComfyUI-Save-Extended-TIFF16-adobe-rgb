# Conflict Clearance Plan — Save Image Extended AdobeRGB

## Description

This plan eliminates all naming, import, and registration conflicts between the standalone ComfyUI custom node **`save-image-adobe-rgb`** and the reference/example repo **`save-image-extended-comfyui`** (by AudioscavengeR, v2.88) so that both can coexist in `custom_nodes/` — or our node can operate completely independently without any trace of the reference.

Seven conflicts have been identified across Python module naming, ComfyUI registration metadata, dependency declarations, frontend extension interference, and registry metadata. Each is documented below with root cause analysis, exact file diffs, and implementation steps.

---

## Conflict Inventory

| # | Conflict | Severity | File(s) |
|---|----------|----------|---------|
| C1 | Module filename prefix overlap (`save_image_extended_*`) | **Critical** | `save_image_extended_adobeRGB.py`, `__init__.py` |
| C2 | Missing `__init__.py` ComfyUI metadata docstring | **High** | `__init__.py` |
| C3 | Phantom `piexif` dependency — not imported, causes install failures | **High** | `requirements.txt`, `pyproject.toml` |
| C4 | Reference JS web extensions hook ALL `CATEGORY='image'` nodes | **Medium** | `save_image_extended_adobeRGB.py` |
| C5 | `WEB_DIRECTORY = None` not in `__all__` export list | **Low** | `__init__.py` |
| C6 | Incomplete `pyproject.toml` registry metadata | **Medium** | `pyproject.toml` |
| C7 | Console log prefix could confuse users during debugging | **Low** | `save_image_extended_adobeRGB.py` (after rename) |

---

## Functionality — Step-by-Step Resolution

### Step 1 — Rename Main Module File (Resolves C1, C7)

**Root Cause:** Our main module is named `save_image_extended_adobeRGB.py`. The reference module is `save_image_extended.py`. Both share the `save_image_extended` prefix. ComfyUI's custom node loader adds each `custom_nodes/` subdirectory to `sys.path` and uses `importlib` for discovery. The shared prefix creates import shadowing risk — particularly on systems where Python's module cache (`sys.modules`) retains partial matches during ComfyUI's sequential loading. This is the most likely root cause of user-reported import failures when both nodes are installed.

**Fix:** Rename the file to a completely distinct name with zero prefix overlap.

**Action:**
```
RENAME: save_image_extended_adobeRGB.py  →  adobergb_save_node.py
```

Inside the renamed file `adobergb_save_node.py`, update the console log prefix from `[save_image_adobeRGB]` to `[adobeRGB-save]` for all print statements (resolves C7 simultaneously):

**Find all occurrences of:**
```python
[save_image_adobeRGB]
```
**Replace with:**
```python
[adobeRGB-save]
```

There are 4 print statements to update (the AVIF/JXL support messages near the top of the file):

```python
# Line ~24 (AVIF fail)
print(f"\033[92m[adobeRGB-save]\033[0m AVIF not supported. pip install pillow-avif-plugin")

# Line ~26 (AVIF success)
print(f"\033[92m[adobeRGB-save] AVIF supported\033[0m")

# Line ~33 (JXL fail)
print(f"\033[92m[adobeRGB-save]\033[0m JXL not supported. pip install pillow-jxl-plugin")

# Line ~35 (JXL success)
print(f"\033[92m[adobeRGB-save] JXL supported\033[0m")
```

---

### Step 2 — Rewrite `__init__.py` (Resolves C1, C2, C5)

**Root Cause (C2):** ComfyUI Manager and the ComfyUI node loader read metadata from the `__init__.py` docstring (`@author`, `@title`, `@nickname`, `@description`). Our file has none. Without these, ComfyUI Manager cannot properly identify, deduplicate, or display our node in its registry — and may silently skip it during loading.

**Root Cause (C5):** `WEB_DIRECTORY` is set to `None` but not included in `__all__`, which some ComfyUI versions inspect to determine whether to scan for web extensions.

**Fix:** Replace `__init__.py` entirely:

```python
"""
@author: [Your Name / Handle]
@title: Save Image Extended AdobeRGB
@nickname: AdobeRGB Save
@description: Save images with color space control (sRGB / Adobe RGB 1998) and bit depth (8/16-bit). Standalone node — no dependencies on Save Image Extended.
"""

from .adobergb_save_node import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = None

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
```

Key changes:
- Import path updated to `adobergb_save_node` (matches Step 1 rename)
- Full ComfyUI metadata docstring with unique `@title` and `@nickname`
- `WEB_DIRECTORY` included in `__all__` export list
- No side-effect imports (no `aiohttp`, no `server` — we don't need them)

---

### Step 3 — Remove Phantom `piexif` Dependency (Resolves C3)

**Root Cause:** `piexif` is listed in both `requirements.txt` and `pyproject.toml` dependencies but is **never imported or used** anywhere in `save_image_extended_adobeRGB.py` (confirmed via grep — zero matches). The reference repo also has it commented out. Our EXIF implementation uses Pillow's native `Image.getexif()` / `.tobytes()` which requires no external library. The `piexif` package can fail to install on some platforms (build-time C extensions), causing users to report install failures that have nothing to do with our actual code.

**Fix `requirements.txt`** — remove `piexif` line:

```
numpy
imagecodecs
tifffile
pillow
pillow-avif-plugin
pillow-jxl-plugin
```

**Fix `pyproject.toml`** — remove `"piexif",` from dependencies array:

```toml
dependencies = [
  "numpy",
  "imagecodecs",
  "tifffile",
  "pillow",
  "pillow-avif-plugin",
  "pillow-jxl-plugin",
]
```

---

### Step 4 — Insulate from Reference JS Extensions (Resolves C4)

**Root Cause:** The reference repo ships `web/js/help_popup.js` which registers a `SIE.HelpPopup` frontend extension. This extension hooks `beforeRegisterNodeDef` for **every node** whose `category` starts with `"image"`:

```javascript
// Reference: help_popup.js line 49-68
const categories = ["image"];
// ...
if (nodeData?.category?.startsWith(category)) {
    addDocumentation(nodeData, nodeType);
}
```

This modifies prototype methods (`onDrawForeground`, `onMouseDown`, `onRemoved`) on our `SaveImageExtendedAdobeRGB` node class in the frontend — even though we don't ship any web extensions. If the reference's `marked.min.js` or `purify.min.js` fail to load (network/path issues), the resulting JS error can prevent **all** image-category nodes from rendering in the UI, which users would perceive as our node "failing to import."

**Fix:** Change our node's `CATEGORY` to use a subcategory that does **not** match the `startsWith("image")` check used by the reference's JS. The reference checks `startsWith("image")` — so we need a category that doesn't begin with the literal string `"image"`.

In the renamed `adobergb_save_node.py`, change:

```python
# BEFORE
CATEGORY = 'image'

# AFTER
CATEGORY = 'Image/AdobeRGB'
```

**Why `Image/AdobeRGB`:** The capital `I` means `"Image/AdobeRGB".startsWith("image")` returns `false` in JavaScript (case-sensitive). ComfyUI's node menu uses this as a path — users will see our node under **Image > AdobeRGB** in the add-node menu, which is both correct and discoverable. Many ComfyUI custom nodes use capitalized category paths (e.g., `"Image/Transform"`, `"Image/Postprocessing"`).

> **Note:** If you prefer to stay in the flat `image` category alongside the built-in Save Image node, you can skip this step — but the reference's JS hooks will still fire on our node when both are installed. The risk is cosmetic (unwanted help popup icon) rather than functional, but it can cause JS errors on edge cases.

---

### Step 5 — Complete `pyproject.toml` Registry Metadata (Resolves C6)

**Root Cause:** The `pyproject.toml` is missing `Repository` URL, `PublisherId`, and `Icon`. ComfyUI Registry and ComfyUI Manager use these to uniquely identify and display nodes. Incomplete metadata can cause the manager to confuse our node with similarly-named packages.

**Fix — replace entire `pyproject.toml`:**

```toml
[project]
name = "save-image-adobe-rgb"
version = "1.0.1"
description = "Save images with Adobe RGB / sRGB color space and 8/16-bit depth control for ComfyUI."
license = { text = "MIT" }
requires-python = ">=3.9"
dependencies = [
  "numpy",
  "imagecodecs",
  "tifffile",
  "pillow",
  "pillow-avif-plugin",
  "pillow-jxl-plugin",
]

[project.urls]
Repository = "https://github.com/YOUR_USERNAME/save-image-adobe-rgb"

[tool.comfy]
PublisherId = "YOUR_PUBLISHER_ID"
DisplayName = "Save Image Extended AdobeRGB"
Icon = ""
```

> Replace `YOUR_USERNAME` and `YOUR_PUBLISHER_ID` with actual values before publishing. Bump version to `1.0.1` to signal the conflict-clearance changes.

---

### Step 6 — Update Version String in Module

In the renamed `adobergb_save_node.py`, update the version to match `pyproject.toml`:

```python
# BEFORE
version = "1.0.0"

# AFTER
version = "1.0.1"
```

This ensures the display name shown in ComfyUI (`Save Image Extended AdobeRGB 1.0.1`) matches the registry version.

---

## Technical Implementation — File Change Summary

### Files Modified

| File | Action | Changes |
|------|--------|---------|
| `save_image_extended_adobeRGB.py` | **Rename** to `adobergb_save_node.py` | File rename only |
| `adobergb_save_node.py` | **Edit** | Update `version`, `CATEGORY`, 4x print prefixes |
| `__init__.py` | **Rewrite** | Full replacement (metadata docstring, import path, `__all__`) |
| `requirements.txt` | **Edit** | Remove `piexif` line |
| `pyproject.toml` | **Rewrite** | Remove `piexif`, add URLs, bump version |

### Files NOT Modified

| File | Reason |
|------|--------|
| Node class name `SaveImageExtendedAdobeRGB` | Already unique — no conflict with `SaveImageExtended` |
| `NODE_CLASS_MAPPINGS` key | Already unique |
| `NODE_DISPLAY_NAME_MAPPINGS` value | Already unique |
| `FUNCTION = 'save_images'` | Internal method name — scoped to class, no conflict |
| Color conversion functions | Module-scoped, unique names, no conflict |
| ICC profile builder | Module-scoped, unique names, no conflict |

---

## Final File State After All Steps

### `__init__.py`
```python
"""
@author: [Your Name / Handle]
@title: Save Image Extended AdobeRGB
@nickname: AdobeRGB Save
@description: Save images with color space control (sRGB / Adobe RGB 1998) and bit depth (8/16-bit). Standalone node — no dependencies on Save Image Extended.
"""

from .adobergb_save_node import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = None

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
```

### `requirements.txt`
```
numpy
imagecodecs
tifffile
pillow
pillow-avif-plugin
pillow-jxl-plugin
```

### `pyproject.toml`
```toml
[project]
name = "save-image-adobe-rgb"
version = "1.0.1"
description = "Save images with Adobe RGB / sRGB color space and 8/16-bit depth control for ComfyUI."
license = { text = "MIT" }
requires-python = ">=3.9"
dependencies = [
  "numpy",
  "imagecodecs",
  "tifffile",
  "pillow",
  "pillow-avif-plugin",
  "pillow-jxl-plugin",
]

[project.urls]
Repository = "https://github.com/YOUR_USERNAME/save-image-adobe-rgb"

[tool.comfy]
PublisherId = "YOUR_PUBLISHER_ID"
DisplayName = "Save Image Extended AdobeRGB"
Icon = ""
```

### `adobergb_save_node.py` (renamed from `save_image_extended_adobeRGB.py`)
Changes within the file (all other code unchanged):
```python
# Line 15 — version bump
version = "1.0.1"

# Line ~24 — AVIF fail message
print(f"\033[92m[adobeRGB-save]\033[0m AVIF not supported. pip install pillow-avif-plugin")

# Line ~26 — AVIF success message
print(f"\033[92m[adobeRGB-save] AVIF supported\033[0m")

# Line ~33 — JXL fail message
print(f"\033[92m[adobeRGB-save]\033[0m JXL not supported. pip install pillow-jxl-plugin")

# Line ~35 — JXL success message
print(f"\033[92m[adobeRGB-save] JXL supported\033[0m")

# Line ~522 — Category
CATEGORY = 'Image/AdobeRGB'
```

---

## Testing Scenarios

### Test 1 — Standalone Installation
1. Place only `save-image-adobe-rgb/` in `custom_nodes/`
2. Start ComfyUI
3. Verify node appears under **Image > AdobeRGB** in add-node menu
4. Verify display name shows `Save Image Extended AdobeRGB 1.0.1`
5. Add the node, connect to a VAE Decode output, run a generation
6. Confirm output saves correctly in sRGB and Adobe RGB modes, both 8-bit and 16-bit

### Test 2 — Co-Installation with Reference
1. Place both `save-image-adobe-rgb/` AND `save-image-extended-comfyui/` in `custom_nodes/`
2. Start ComfyUI
3. Verify **both** nodes appear — ours under **Image > AdobeRGB**, reference under **image**
4. Verify no Python import errors in the console
5. Verify no JS errors in browser dev console
6. Run a workflow using both nodes simultaneously — confirm both save correctly

### Test 3 — Dependency Installation
1. Fresh Python environment with only ComfyUI base
2. `pip install -r requirements.txt` for our node
3. Confirm no `piexif` build errors
4. Confirm `tifffile` and `imagecodecs` install cleanly
5. Confirm graceful degradation messages when optional plugins (`pillow-avif-plugin`, `pillow-jxl-plugin`) are absent

### Test 4 — ComfyUI Manager Discovery
1. Install via ComfyUI Manager (if published) or manual git clone
2. Verify node appears in Manager's installed nodes list
3. Verify metadata (`@title`, `@description`) displays correctly
4. Verify no duplicate entries or confusion with reference node

---

## Architecture Decisions

### Why rename the module file instead of just the class?
ComfyUI's loader uses `importlib` with directory-based module discovery. While Python's relative imports (`from .module import ...`) are package-scoped, ComfyUI adds each `custom_nodes/` subdirectory to `sys.path`. Two modules starting with `save_image_extended` in the same `sys.path` creates ambiguity in Python's import resolution. A completely distinct filename (`adobergb_save_node.py` vs `save_image_extended.py`) eliminates this class of bugs entirely.

### Why change CATEGORY to `Image/AdobeRGB`?
The reference's `help_popup.js` uses `nodeData?.category?.startsWith("image")` (lowercase) to hook into nodes. JavaScript's `startsWith` is case-sensitive. Using `Image` (capitalized) avoids the hook while maintaining discoverability. ComfyUI's add-node menu supports hierarchical categories via `/` — this puts our node in a clean subcategory.

### Why not just delete the reference repo?
Users may have both installed independently via ComfyUI Manager. We must ensure our node works regardless of what else is in `custom_nodes/`. The goal is conflict-proof isolation, not assuming a clean environment.

---

## Implementation Order

Execute steps in this exact order to avoid intermediate broken states:

1. **Step 1** — Rename the Python file (OS-level rename)
2. **Step 2** — Rewrite `__init__.py` (updates import path)
3. **Step 3** — Fix `requirements.txt` and `pyproject.toml` dependencies
4. **Step 4** — Edit `CATEGORY` in the renamed module
5. **Step 5** — Complete `pyproject.toml` metadata
6. **Step 6** — Bump version string in module
7. **Test** — Run Test Scenarios 1-4
8. **Clean** — Delete `__pycache__/` directory to clear stale bytecode
