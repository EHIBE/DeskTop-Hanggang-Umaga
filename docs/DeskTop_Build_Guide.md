# DeskTop: Hanggang Umaga | Step-by-Step Build Guide

**Companion to `DeskTop_PRD.md`.** The PRD says *what* to build. This guide says *how*, in order.

| | |
|---|---|
| Written | Oct 27, 2026, 11:00 PM SGT |
| Hard deadline | **Nov 5, 10:00 AM SGT** (Nov 5, 02:00 UTC, Nov 4 9:00 PM ET) |
| Your target | **Nov 4, 11:00 PM SGT** (15:00 UTC, 10:00 AM ET) |
| Platform | Windows laptop |

---

## How to use this guide

- Work the phases in order. Each phase ends with a **Done when** check. Do not start the next phase until it passes, unless the **If stuck** line says to move on
- Feature IDs (FR-xx, F0x) point to the PRD
- Code snippets are starting points, not final code. Anything marked **verify** was not confirmed in Meta's docs
- If you already finished a phase, skip it

---

## The honest schedule

The PRD planned Oct 27 as day 1 of coding. That day is over. The plan below fits the same Must list into Oct 28 to Nov 4, with three Should features cut now and the freeze moved from Nov 2 to Nov 3.

**Cut now (decided, not optional)**

| Cut | Replacement |
|---|---|
| F22 Lost detection | Objects off the desk keep their last position |
| F12 Spark fallback parser | Local grammar plus tap controls |
| Kapre smoke | Kapre is a big slow hitter with no smoke |
| Every Could (F16, F19, F20, F21, F23) | Not built |

**Schedule (SGT)**

| Date | Hours | Phases | Must pass by end of day |
|---|---|---|---|
| Oct 27 (Tue) night | 1.5 | Phase 0 | Tools installed, rules read, key works |
| Oct 28 (Wed) | 7 | Phases 1, 2, 3 | Every API smoke test passes. Warped desk feed shows in the Electron window |
| Oct 29 (Thu) | 7 | Phase 4, start Phase 5 | 5 objects register with masks and unit cards |
| Oct 30 (Fri) | 7 | Finish Phase 5, Phase 6 | Sprites on objects. Sprites follow your hand. End Turn re-anchors |
| Oct 31 (Sat) | 10 | Phase 7, start Phase 8 | Rules tests green. A night runs through every state |
| Nov 1 (Sun) | 10 | Finish Phase 8, Phases 9, 10, **Playtest 1** | Full 8-turn night by tap with narration |
| Nov 2 (Mon) | 8 | Phases 11, 12 | Voice orders work. Tikbalang push and duwende steal work |
| Nov 3 (Tue) | 8 | Phase 13, evals, fixes. **Freeze 6:00 PM SGT** (10:00 UTC, 5:00 AM ET). **Playtest 2 and demo recording tonight** | 3 crash-free nights. Raw demo footage saved twice |
| Nov 4 (Wed) | 8 | Phases 14, 15 | Reel rendered. Video, README and submission done by 11:00 PM SGT |
| **Total** | **66.5** | | |

**This is more hours than the PRD's 63.** About 7 to 10 hours a day with the PayPal hackathon and thesis running too. If a day slips, use the cut order at the end of this guide the same day. Do not push the freeze.

---

## Phase 0: Before you write code (tonight, 1.5 h)

### 0.1 Account and rules checks

1. Open the acceptance email and your Cerebral Valley participant page
2. Read and accept the Official Rules. They are not on the public page, so look in the email, the participant dashboard or Discord
3. Check each item below against the rules and write the answer next to it in `docs/rules-notes.md`

| Item | What some teams' public notes say (unconfirmed) | PRD default |
|---|---|---|
| Demo video length | 3 minutes, the main judging artifact | 2:30 |
| Repo | Public repo required | Public |
| Pre-existing code | Only work built during the event counts | New repo after kickoff |
| Model use | Pass/fail check that the project truly uses Meta Model API or open weights | 4 Meta models |
| Credits | Must be claimed by Nov 4 | Claim tonight |
| Team | Max 4, one submission per team | Solo |

4. Claim the $150 Model API credits in the Model API dashboard tonight
5. Create an API key at dev.meta.ai. Store it in a password manager. Never paste it in code or chat
6. Confirm your account is in **Standard mode**, not Contributor mode. If you use Muse Code, turn Contributor mode off in its settings

**If a rule conflicts with the PRD**: paste the rule text into the OFFICIAL_RULES slot of `DeskTop_PRD_Prompt.md` and regenerate, or adjust the matching phase by hand.

### 0.2 Install tools (Windows)

Install these if missing. Run each check in PowerShell.

| Tool | Check | Notes |
|---|---|---|
| Git | `git --version` | |
| Node.js LTS | `node -v` | 20 or newer |
| Python 3.11 | `py -3.11 --version` | 3.10 or newer is required by `meta-sam-parser` |
| ffmpeg | `ffmpeg -version` | Add the `bin` folder to PATH |
| VS Code | | Plus Python and ESLint extensions |

### 0.3 Physical setup

- A plain matte mat or desk, about 60 x 40 cm clear
- Camera stand or clamp, camera 45 to 70 cm above the desk looking straight down. A phone used as a webcam works
- One A4 sheet
- Demo objects: mug, coin, keys, pen, eraser. No identical pairs
- A lamp for even light

### 0.4 Repo

```powershell
mkdir DeskTop-Hanggang-Umaga
cd DeskTop-Hanggang-Umaga
git init
mkdir backend, backend\rules, backend\tests, assets, fixtures, eval, docs
copy ..\DeskTop_PRD.md docs\
```

Create `.gitignore`:

```gitignore
.env
*.key
node_modules/
.venv/
__pycache__/
recordings/
userdata/
*.sqlite
```

Push to a new **public** GitHub repo under EHIBE. Commit early and often. The commit history is your proof that the code was written during the event.

**Done when**: rules notes written, credits claimed, `py -3.11`, `node`, `ffmpeg` all print versions, empty repo pushed.

---

## Phase 1: API smoke tests (Oct 28, 1.5 h)

**Goal**: prove every Meta call works before building on it. Save each raw response as a fixture for tests.

### 1.1 Python environment

```powershell
cd backend
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install fastapi "uvicorn[standard]" websockets openai opencv-contrib-python numpy pillow shapely pydantic sounddevice meta-sam-parser python-dotenv rapidfuzz pytest
pip freeze > requirements.txt
```

- Install `opencv-contrib-python` only. Do not also install `opencv-python`. The contrib build has the CSRT and KCF trackers
- Create `backend/.env` with `MODEL_API_KEY=...` for development only. It is git-ignored

### 1.2 Shared client

`backend/meta_client.py`:

```python
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["MODEL_API_KEY"])
```

### 1.3 Muse Spark with structured output (PRD assumption A6)

`backend/smoke/spark.py`:

```python
import json
from meta_client import client

schema = {
    "type": "object",
    "additionalProperties": False,
    "required": ["line_tl", "line_en"],
    "properties": {
        "line_tl": {"type": "string"},
        "line_en": {"type": "string"},
    },
}

r = client.responses.create(
    model="muse-spark-1.3",
    reasoning={"effort": "low"},
    input="Write one spooky Taglish line about an aswang near a bahay kubo.",
    text={"format": {"type": "json_schema", "name": "line", "schema": schema, "strict": True}},
)
print(r.output_text)
json.dump(r.model_dump(), open("../fixtures/spark_line.json", "w"), indent=2)
```

- **Verify**: the docs name `text.format` but do not show a full example. If this returns HTTP 400, switch to Chat Completions with `response_format={"type": "json_schema", "json_schema": {"name": "line", "schema": schema, "strict": True}}` and use that everywhere
- Write down which one worked in `docs/rules-notes.md`

### 1.4 SAM 3.1 image with box prompts

1. Take any desk photo, save as `eval/desk1.jpg`, note its width and height
2. Open it in Paint and read rough pixel corners of 2 objects

`backend/smoke/sam.py`:

```python
import base64
from meta_client import client
from meta_sam_parser import build_object_prompt, PromptObject, FramePrompt, PromptBox

W, H = 1280, 720  # your image size
prompt = build_object_prompt(
    size=(W, H),
    objects=[
        PromptObject(id=1, prompts=[FramePrompt(frame=0, box=PromptBox(400, 300, 490, 400))]),
        PromptObject(id=2, prompts=[FramePrompt(frame=0, box=PromptBox(640, 120, 705, 182))]),
    ],
)
img = base64.b64encode(open("../eval/desk1.jpg", "rb").read()).decode()

text = ""
with client.responses.stream(
    model="sam-3.1",
    input=[{"type": "message", "role": "user", "content": [
        {"type": "input_text", "text": prompt},
        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{img}"},
    ]}],
    metadata={"include_confidence": "true", "mask_encoding": "one_bit"},
) as stream:
    for e in stream:
        if e.type == "response.output_text.delta":
            text += e.delta
print(text[:400])
open("../fixtures/sam_boxes.txt", "w").write(text)
```

- **Verify**: the exact `PromptObject` and `FramePrompt` argument names. Run `python -c "import meta_sam_parser, inspect; help(meta_sam_parser.build_object_prompt)"`. The builder uses **exclusive** right and bottom edges, the wire format uses inclusive. Let the builder handle it
- **Verify**: the Python names of the stream parsers and `decode_mask_to_raster`. Run `python -c "import meta_sam_parser; print(dir(meta_sam_parser))"`
- Each record should look like `<0f>1<|box;...;c=0.96|><|mask;...|>`

### 1.5 Muse Image

`backend/smoke/image.py`:

```python
import base64
from meta_client import client

crop = base64.b64encode(open("../eval/mug_crop.png", "rb").read()).decode()
r = client.responses.create(
    model="muse-image-1.0",
    input=[{"role": "user", "content": [
        {"type": "input_text", "text": "Redraw the object in this photo as one top-down 16-bit pixel art game sprite of a bahay kubo. Keep its main colors and silhouette. Centered, fills about 80% of the frame, no shadow, no text. Solid flat #FF00FF background."},
        {"type": "input_image", "image_url": f"data:image/png;base64,{crop}"},
    ]}],
    tools=[{"type": "image_generation", "enable_web_search": False, "enable_image_search": False,
            "enable_shell": False, "reasoning_strength": "low", "size": "1024x1024", "output_format": "png"}],
)
b64 = next(o.result for o in r.output if o.type == "image_generation_call")
open("../fixtures/sprite_kubo.png", "wb").write(base64.b64decode(b64))
```

Time this call. Write the seconds in `docs/rules-notes.md`. PRD target: 30 s or less.

### 1.6 Muse Voice Transcribe

1. Copy the "Transcribe a microphone" quickstart from dev.meta.ai/docs/speech-to-text into `backend/smoke/voice.py`
2. Change the handshake to `"mode": "DIARIZATION"` and add `"languageBias": ["English", "Tagalog"]` and `"keywords": ["tapos", "aswang", "kubo", "albularyo"]`
3. Run it and have two people speak Taglish for 10 seconds
4. Save the printed events to `fixtures/voice_diar.jsonl`

### 1.7 Files API

```python
from meta_client import client
f = client.files.create(file=open("../eval/clip.mp4", "rb"), purpose="user_data",
                        extra_body={"expires_after": {"anchor": "created_at", "seconds": 86400}})
print(f.id)
client.files.delete(f.id)
```

**Verify**: whether the SDK accepts `expires_after` directly. If not, `extra_body` as above. If both fail, upload without it and rely on the explicit delete.

**Done when**: all 5 smoke tests run, fixtures saved, sprite latency written down.
**If stuck**: post the exact error in the hackathon Discord office hours. Move on to Phase 2 while waiting.

---

## Phase 2: Camera and calibration (Oct 28, 2 h, F01)

**Goal**: a top-down, scaled view of the desk (FR-01 to FR-04).

### 2.1 Capture

`backend/capture.py`:

```python
import cv2

def open_camera(index: int = 0):
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    if not cap.isOpened():
        raise RuntimeError("camera busy or missing")
    return cap
```

### 2.2 Homography from an A4 sheet

The user taps 4 corners of the A4 sheet. Map them to a top-down plane at a fixed scale.

```python
import numpy as np, cv2

PX_PER_CM = 20  # warped image resolution
A4_W, A4_H = 21.0, 29.7

def homography(corners_px, sheet_center_cm):
    """corners_px: 4 points (TL, TR, BR, BL) in camera pixels."""
    cx, cy = sheet_center_cm
    dst = np.float32([
        [cx - A4_W / 2, cy - A4_H / 2], [cx + A4_W / 2, cy - A4_H / 2],
        [cx + A4_W / 2, cy + A4_H / 2], [cx - A4_W / 2, cy + A4_H / 2],
    ]) * PX_PER_CM
    return cv2.getPerspectiveTransform(np.float32(corners_px), dst)

def warp(frame, H, play_w_cm=60, play_h_cm=40):
    return cv2.warpPerspective(frame, H, (int(play_w_cm * PX_PER_CM), int(play_h_cm * PX_PER_CM)))
```

- Default play area 60 x 40 cm, so the warped frame is 1200 x 800 px
- Put the sheet in the middle: `sheet_center_cm = (30, 20)`
- Optional auto-detect: SAM concept prompt `"white paper"`, take the mask's 4 extreme corners. Manual taps are the fallback and fine for the demo

### 2.3 Checks

- Ruler check: place a real ruler, draw a 10 cm line on the warped image. It must match within 0.5 cm
- Save the empty-desk baseline. On each turn compare with `cv2.absdiff` on the desk border. Big change means the camera moved (FR-04)

**Done when**: warped feed is square-on, ruler check passes, calibration saved to SQLite.
**If stuck**: tilt causes skew? Raise the camera and point it straight down. Bad masks later? Switch to a plain single-color mat.

---

## Phase 3: App shell and live stream (Oct 28, 3.5 h)

**Goal**: Electron shows the warped feed streamed from FastAPI.

### 3.1 Scaffold Electron

```powershell
npm create @quick-start/electron@latest app -- --template react-ts
cd app
npm install
npm install -D tailwindcss @tailwindcss/vite
```

Add the Tailwind Vite plugin to the renderer section of `electron.vite.config.ts` and put `@import "tailwindcss";` at the top of the renderer CSS.

**Verify**: the scaffold command and Tailwind steps match the current electron-vite and Tailwind docs. Use their docs if anything differs.

### 3.2 Spawn the backend from Electron main

```ts
import { app, safeStorage } from "electron"
import { spawn } from "child_process"
import crypto from "crypto"

const token = crypto.randomBytes(16).toString("hex")
const apiKey = loadKey() // decrypt with safeStorage.decryptString from userData file
const backend = spawn(pythonPath, ["-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8765"], {
  cwd: backendDir,
  env: { ...process.env, MODEL_API_KEY: apiKey, DESKTOP_TOKEN: token },
})
app.on("before-quit", () => backend.kill())
```

- First-run screen asks for the key, then `safeStorage.encryptString(key)` writes it to the userData folder
- Pass only `token` and the port to the renderer. Never the key (NFR-24)

### 3.3 FastAPI frame stream

`backend/server.py`:

```python
import asyncio, base64, os, cv2
from fastapi import FastAPI, WebSocket

app = FastAPI()
TOKEN = os.environ.get("DESKTOP_TOKEN", "dev")

@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    if sock.query_params.get("token") != TOKEN:
        await sock.close(code=1008)
        return
    while True:
        frame = state.latest_warped  # filled by the capture loop
        if frame is not None:
            ok, jpg = cv2.imencode(".jpg", cv2.resize(frame, (960, 640)), [cv2.IMWRITE_JPEG_QUALITY, 70])
            await sock.send_json({"type": "frame", "jpg": base64.b64encode(jpg).decode(), "poses": state.poses})
        await asyncio.sleep(1 / 25)
```

- Run the camera loop in a background thread that updates `state.latest_warped`
- Renderer draws the JPEG on a `<canvas>`, then sprites on top

**Done when**: Electron window shows the warped desk feed at 20 FPS or more (PRD exit for Oct 27).

---

## Phase 4: Summon pipeline (Oct 29, 5 h, F02)

**Goal**: place an object, say or type a name, get a unit card (FR-06 to FR-10, FR-14 to FR-16).

### 4.1 Steps per summon

1. Player places an object. Wait until there is no hand motion for 1 s (frame difference below a threshold)
2. Take the warped snapshot (1200 x 800)
3. Call Muse Spark with the snapshot, the spoken or typed name, and the known boxes. Use schema `unit_card` from PRD section 12
4. Clamp the box from the 0 to 1000 grid: `x_px = clamp(x, 0, 1000) / 1000 * 1200`, `y_px = clamp(y, 0, 1000) / 1000 * 800`
5. Call SAM with box prompts for **all** known objects plus the new one. Kubo is always ID 1
6. Clamp the card with the rules engine (PRD section 8 class templates and balance caps)
7. Save `object_signature`, `unit` and `night_unit` rows. Show the card with the class placeholder sprite

### 4.2 Spark prompt (summon)

```text
You see a top-down photo of a desk. Known objects are listed with boxes.
Find the ONE object that is not in the known list. The player named it: "{spoken_name}".
Return its box on a 0 to 1000 grid, a short English label, and a unit card.
Pick class and power only from the enums. hp_delta + atk_delta must be 0 or less.
Write card text in natural Taglish and plain English. No gore.
Known objects: {known_boxes_json}
```

Add `"reasoning": {"effort": "medium"}`.

### 4.3 Rules clamp

```python
CLASS = {
  "kubo":   dict(hp=10, atk=0, move=0,  rng=None,    powers=["none"]),
  "charm":  dict(hp=3,  atk=0, move=0,  rng=None,    powers=["P06","P07","P08","P12"]),
  "healer": dict(hp=4,  atk=1, move=8,  rng=5,       powers=["P01","P02"]),
  "fighter":dict(hp=6,  atk=2, move=12, rng=5,       powers=["P03","P05","P11"]),
  "reach":  dict(hp=4,  atk=2, move=12, rng=9,       powers=["P04","P09"]),
  "ranged": dict(hp=3,  atk=1, move=12, rng=15,      powers=["P04","P10","P12"]),
  "scout":  dict(hp=3,  atk=1, move=16, rng=5,       powers=["P08","P11"]),
  "wall":   dict(hp=7,  atk=0, move=8,  rng=None,    powers=["P02","P06"]),
}

def clamp_card(c, is_first):
    cls = "kubo" if is_first else (c["class"] if c["class"] != "kubo" else "fighter")
    t = CLASS[cls]
    hd, ad = c["hp_delta"], c["atk_delta"]
    if hd + ad > 0:  # rule: hp_delta + atk_delta must be 0 or less
        if hd == 1 and ad == 1:
            ad = -1          # tougher, so weaker
        elif hd == 1:
            hd = 0
        else:
            ad = 0
    power = c["power_id"] if c["power_id"] in t["powers"] else t["powers"][0]
    return dict(cls=cls, hp=max(1, t["hp"] + hd), atk=min(3, max(0, t["atk"] + ad)),
                move=t["move"], rng=t["rng"], power=power)
```

Write tests for this today (Phase 7 adds the rest).

### 4.4 Caps

- First summon must become the kubo (FR-15)
- Max 12 objects, max 2 charms, max 2 walls (FR-16)
- If Spark says `found_new: false`, show "Alin ang bago? I-tap mo." and use the tapped box (FR-14)

**Done when**: 5 objects registered with masks and cards, card in 8 s or less.
**If stuck**: Spark boxes poor? Make tap-to-select the main path and keep Spark only for the label and card.

---

## Phase 5: Sprite pipeline (Oct 29 to 30, 4 h, F03)

**Goal**: each unit gets a keyed 48 x 48 sprite in one style (FR-11 to FR-13).

### 5.1 Before the pipeline

- Make 8 class placeholder sprites (one per class) and the 5 enemy sprites with Muse Image now, key them, and commit them to `assets/`. These are your fallbacks and your Demo Safe Mode art

### 5.2 Pipeline per unit (background task)

1. Crop the warped frame to the mask box padded 15%
2. Fill outside the mask with `#808080`
3. Resize long side to 512 px
4. Key color: `#FF00FF`, or `#00FF00` if the object's main hue is within 30 degrees of magenta
5. Call Muse Image (Phase 1.5 shape). After the first good sprite, add it as a second `input_image` and the line "Match the pixel art style of the second image."
6. Key out the background:

```python
import numpy as np
from PIL import Image

def chroma_key(img: Image.Image, key=(255, 0, 255), tol=60):
    a = np.array(img.convert("RGBA")).astype(int)
    dist = np.abs(a[..., :3] - np.array(key)).sum(axis=2)
    a[..., 3] = np.where(dist < tol * 3, 0, 255)
    return Image.fromarray(a.astype("uint8"))
```

7. Erode alpha by 1 px, trim, downscale with `Image.NEAREST` into a 48 x 48 canvas
8. Quantize to the Gabi 16 palette plus 8 object colors, add a 1 px `#0B0E1A` outline
9. Validate: alpha coverage 15% to 90%. Fail → retry once with the other key color → fail → keep placeholder
10. Save with cache key `sha256(signature_id|name|class|palette_v|prompt_v)`. Swap placeholder for the real sprite

### 5.3 Cost tracker (F18, 1 h)

Write every call to the `api_usage` table with the PRD section 12 prices. Warn at $90. Block paid calls at $120 and switch to Demo Safe Mode.

**Done when**: 10 objects get sprites, 8 or more look right, every call is logged with cost.
**If stuck**: sprites slow or ugly? Pre-generate sprites for the 5 demo objects and cache them.

---

## Phase 6: Tracking and re-anchor (Oct 30 to 31, 7 h, F04 + F05)

**Goal**: sprites follow hands between turns. SAM fixes positions at End Turn (FR-26 to FR-29).

### 6.1 Tracker

```python
import cv2

def make_tracker():
    return cv2.TrackerKCF_create()  # try TrackerCSRT_create if KCF drifts

trackers = {}  # sam_id -> tracker

def init_trackers(frame_small, boxes_small):
    for sid, (x, y, w, h) in boxes_small.items():
        t = make_tracker()
        t.init(frame_small, (x, y, w, h))
        trackers[sid] = t

def update(frame_small):
    out = {}
    for sid, t in trackers.items():
        ok, box = t.update(frame_small)
        out[sid] = (ok, box)
    return out
```

- Track on the warped frame resized to 640 x 427 (scale boxes by 640/1200)
- Smooth sprite positions with an exponential moving average (alpha 0.4)
- `ok == False`: freeze the sprite (FR-27). After 5 s with no hand motion, run one SAM call for that object
- Benchmark: with 12 trackers you need 10 updates per second or more. If CSRT is too slow, use KCF

### 6.2 End Turn re-anchor

1. Wait for no hand motion for up to 3 s ("Tanggalin muna ang kamay sa mesa.")
2. One SAM image call with every object's tracker box padded 20%, under its SAM ID
3. Per object, apply the PRD section 12 logic:

| Condition | Action |
|---|---|
| Confidence 0.5 or more and IoU with tracker 0.3 or more | Accept SAM, snap sprite, re-init tracker |
| Confidence 0.5 or more, IoU under 0.3 | Accept only if color histogram matches (Bhattacharyya 0.35 or less) |
| Low confidence | Retry with a point prompt at the tracker center |
| Still low | Concept prompt with the object label, pick closest histogram within 15 cm |
| Still nothing | Keep tracker position, show "?" and ask for a tap |

4. Convert mask centroid to cm: `x_cm = x_px / 20`, `y_cm = y_px / 20`

**Done when**: slide 6 objects around, sprites follow, re-anchor gets 20 of 20 identities right.
**If stuck**: identity swaps on similar objects? Remove look-alike objects from the demo set and move on.

---

## Phase 7: Rules engine, turn loop, HUD (Oct 31, 6 h, F06)

**Goal**: deterministic game logic with tests (FR-05, FR-31 to FR-34, FR-37, FR-40).

### 7.1 Rules engine layout

`backend/rules/` with pure functions only. No I/O, no time, no randomness.

| File | Contents |
|---|---|
| `geometry.py` | Edge-to-edge distance with shapely (mask convex hull for units, circle r = 2 cm for enemies), move distance from start centroid, +1 cm tolerance |
| `units.py` | Class templates, clamp, powers P01 to P12 with cooldowns |
| `enemies.py` | Stats, AI target rules, movement toward target stopping at range, walls block paths |
| `waves.py` | Wave table for 8 turns, scaling for player count and difficulty |
| `resolve.py` | `resolve_turn(state, intents) -> (new_state, events)` |

```python
from shapely.geometry import Polygon, Point

def edge_distance_cm(unit_hull_cm: list[tuple[float, float]], enemy_xy_cm: tuple[float, float]) -> float:
    return max(0.0, Polygon(unit_hull_cm).distance(Point(enemy_xy_cm)) - 2.0)

def in_range(dist_cm: float, range_cm: float) -> bool:
    return dist_cm <= range_cm + 1.0
```

### 7.2 Turn order (from PRD section 7 and 8)

1. Spawn and telegraph (enemies move, intent arrows)
2. Player phase (hands move, orders queue as chips)
3. End Turn snapshot and re-anchor
4. Validate moves. Illegal → back to player phase with ghost (FR-33)
5. Resolve player intents in confirmed order
6. Enemies attack telegraphed targets only if still in range, else "Nakaiwas!"
7. Physical effects (Phase 12)
8. Win and lose check, autosave

Damage: `max(1, ATK + bonuses - shield)`. No dice.

### 7.3 State machine

Implement the states from PRD section 8 as an enum with one `transition(event)` function. Every state change writes a `turn_log` row with `t_ms` so you can measure latency later.

### 7.4 HUD

Renderer components: turn counter, phase banner, kubo HP bar, unit HP and cooldown strip, intent arrows with damage numbers, move rings (solid green with a check, dashed red with an X), speaker chip, order chips, End Turn button. All text from one `copy.ts` file using the PRD copy deck keys.

### 7.5 Tests

```powershell
pytest backend/tests -q
```

Must cover: distance, move legality, damage with shield, each power, each enemy AI, each wave, win, lose, and determinism (same state and intents twice give the same events, E7).

**Done when**: tests green, a night runs through every state with stub enemies.

---

## Phase 8: Core enemies and waves (Oct 31 to Nov 1, 2 h, F07)

**Goal**: Aswang and Manananggal with telegraphing (FR-35).

| Enemy | Implement |
|---|---|
| Aswang | HP 3, ATK 2, move 15 cm, target isolated unit (no ally within 10 cm), else lowest HP, else kubo |
| Manananggal | Upper (HP 4, ATK 2, move 20 cm, flies over walls) and lower (HP 3, does not move). Lower dies → both end at turn end. Upper dies, lower lives → re-forms after 2 turns |
| Tikbalang, Duwende | Stats now, special effects in Phase 12 |
| Kapre | HP 8, ATK 3, move 5 cm, range 9 cm, targets kubo. No smoke (cut) |

Use the PRD wave table. Spawn on the named desk edge inside the 5 cm forest border.

**Done when**: a full 8-turn night runs with all waves and correct arrows.

---

## Phase 9: GM narration (Nov 1, 3 h, F09)

**Goal**: Taglish narration that never blocks play (FR-38, FR-39).

1. Write the system prompt from PRD section 12 GM contract. Keep it stable so it caches
2. After each resolution, send the board state and `events` list as JSON. Use `previous_response_id` to chain the night. `reasoning.effort: "low"`
3. Schema `gm_turn`, with `entity_id` enum built from current IDs
4. Validate with Pydantic. Drop any callout ID not in state. One repair retry, then a line bank line
5. Start animations from rules events right away. Show narration when it arrives. Timeout 20 s

```python
import asyncio

async def narrate(payload):
    try:
        return await asyncio.wait_for(call_gm(payload), timeout=20)
    except Exception:
        return line_bank.pick(payload["events"])
```

6. Put every line from PRD section 8 GM line bank into `assets/lines.json`

**Done when**: every turn shows a caption within 6 s, or a line bank line.

---

## Phase 10: Safety features (Nov 1, 5 h, F13, F14, F17, F24)

| Feature | Steps | Done when |
|---|---|---|
| Tap controls (FR-25) | Tap a unit, pick attack, power or heal, tap a target. Same chip as voice | Whole night playable with taps only |
| Autosave (FR-41) | One SQLite transaction at the end of each turn | Kill the backend at turn 5, restart, resume at turn 5 |
| Demo Safe Mode (FR-50) | Toggle: cached sprites and cards, line bank, local grammar, tap. Optional SAM off (tracker only) | A night completes with Wi-Fi off |
| Delete data (FR-52) | Delete campaign rows, sprites, recordings | No files remain |

### Playtest 1 (Nov 1 evening, 1 h)

- 2 friends, taps only
- Measure: setup time, turn time, confusing moments, fun 1 to 5, unfair rules
- Write notes in `docs/playtests.md`. Fix only rule bugs tonight

---

## Phase 11: Voice (Nov 2, 4 h, F10)

**Goal**: Taglish orders by voice (FR-17, FR-19, FR-20, FR-22, FR-24).

### 11.1 Two sessions per night

| Phase | Mode | Keywords |
|---|---|---|
| Summon | `ENDPOINTING` | Class names, common objects, creature names |
| Night | `DIARIZATION` | Plus every unit name and player name |

Keywords are fixed at session start, so open a new session after summon.

### 11.2 Audio loop

- sounddevice at 24,000 Hz, mono, int16, 80 ms blocks (3,840 bytes)
- Send in real time. Send silence frames while paused, or the server closes the stream
- Handle close codes: 1008 fix config, 1011 retry or new session at 60 min, 1013 back off

### 11.3 Events to UI

- `transcript` partials replace the caption, never append
- `speechComplete` gives the final text for a `turnId`
- `speaker` gives the label for that turn

### 11.4 Local grammar

```python
from rapidfuzz import process, fuzz

VERBS = {
  "attack": ["atake", "saksakin", "tira", "hampasin", "banatan", "attack", "hit"],
  "power":  ["gamitin", "protektahan", "bantayan", "power", "use"],
  "heal":   ["gamutin", "pagalingin", "heal"],
  "end_turn": ["tapos", "tapos na", "end turn", "done"],
  "cancel": ["hindi", "cancel", "mali", "wag"],
}

def parse(text, unit_names, enemy_names):
    t = text.lower()
    action = next((a for a, ws in VERBS.items() if any(w in t for w in ws)), None)
    unit = process.extractOne(t, unit_names, scorer=fuzz.partial_ratio, score_cutoff=75)
    target = process.extractOne(t, enemy_names + unit_names, scorer=fuzz.partial_ratio, score_cutoff=75)
    return action, unit and unit[0], target and target[0]
```

- Every parsed order becomes a chip. "Hindi" cancels the speaker's last chip
- Hold Space for push-to-talk as a fallback (FR-24)

**Done when**: 40 of 50 recorded test orders are parsed right (E3).
**If stuck**: diarization flaky? Use ENDPOINTING with tap-to-claim and keep going.

---

## Phase 12: Voice claim and physical enemies (Nov 2, 4 h, F11 + F08)

### 12.1 Voice claim (FR-18, FR-23)

1. At night start, prompt "Isa-isa: Ako si [pangalan], hawak ko ang..."
2. Regex `ako si (\w+)` on `speechComplete`. Map that turn's speaker label to the player
3. Fuzzy-match unit names after "hawak ko ang" to set owners
4. Two open turnIds at once → drop both, show "Isa-isa lang!"
5. Skip button → players tap their names

### 12.2 Tikbalang push

1. On hit, compute the target spot 8 cm straight away from the tikbalang
2. Draw a ghost outline there with "Usugin ang [object] sa may anino."
3. Wait until the tracker shows the object within 2 cm, or 20 s
4. Target off the desk → unit is out for 1 turn, no move needed

### 12.3 Duwende steal

1. On hit, the unit is stolen. Show "Tanggalin muna sa mesa."
2. Duwende flees 12 cm per turn to the nearest edge
3. Killed → show a return mark, "Ibalik sa may marka."
4. Escapes → unit lost for the night

**Done when**: both effects work in a test night.
**If stuck**: cut duwende steal first (cut order), keep tikbalang push.

---

## Phase 13: Recording, evals, freeze, demo night (Nov 3, 8 h)

### 13.1 Recorder and consent (2 h, FR-44, FR-45)

- Consent screen before the night: each claimed player taps Payag
- Pipe warped frames to ffmpeg:

```python
import subprocess

def start_recorder(path, w=1200, h=800, fps=25):
    return subprocess.Popen([
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(fps),
        "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", path,
    ], stdin=subprocess.PIPE)

# each frame: rec.stdin.write(warped.tobytes())
```

- Show a red REC dot while recording

### 13.2 Evals (1.5 h)

| Eval | Quick version for today |
|---|---|
| E1 registration | 20 objects, 1 condition, count correct |
| E2 re-anchor | 50 End Turns from test nights |
| E3 Taglish | 50 recorded orders, 2 speakers |
| E4 GM validity | Count `gm_invalid` rows in turn_log |
| E7 determinism | Already in pytest |

Write the numbers in `docs/eval.md`. They go in the README and the video.

### 13.3 Fixes (2 h)

Only crash bugs and demo-visible bugs. No new features.

### 13.4 Freeze at 6:00 PM SGT (10:00 UTC, 5:00 AM ET)

`git tag freeze-nov3` and push.

### 13.5 Playtest 2 and demo recording (2.5 h, evening)

Run the dry-run checklist from PRD section 18 first. Then:

1. 2 or 3 Filipino friends, full build with voice and recording on
2. Get a written OK from each friend to appear in the video
3. Screen-record the app at 1080p 30 FPS with audio
4. Phone on a tripod films the table from the side for B-roll
5. Play at least 2 full nights. Save every file to 2 drives
6. Ask: "Would you post this replay?" and the fun 1 to 5

**Done when**: 2 complete nights recorded, footage backed up.

---

## Phase 14: Replay reel (Nov 4 morning, 4 h, F15)

**Goal**: a 30 to 60 s reel from the Nov 3 footage (FR-46 to FR-48). Post-processing only, so it does not break the freeze.

1. Pick 4 to 6 highlights from turn_log (kubo hits, kills, manananggal split, last turn), about 8 s each
2. Build a 10 FPS proxy:

```powershell
ffmpeg -ss <start> -t 8 -i night.mp4 -vf "fps=10,scale=960:-2" -c:v libx264 -movflags +faststart seg1.mp4
# repeat per segment, then join with a concat list:
ffmpeg -f concat -safe 0 -i list.txt -c copy proxy.mp4
```

3. Upload `proxy.mp4` with `expires_after` 86,400 s
4. One SAM video request with box prompts at the first frame of each segment (`<Nf>` markers via `build_object_prompt`), `propagation_direction: "forward"`, streaming
5. Delete the uploaded file
6. Render locally at 1080p 30 FPS: original footage, sprites pinned to SAM tracks (interpolate boxes between the 10 FPS frames), damage numbers from turn_log, dawn title card
7. Export MP4, 60 s max

**If stuck**: keep one 10 s SAM-tracked clip and move to Phase 15 by 2:00 PM SGT.

---

## Phase 15: Video, README, submission (Nov 4, 4 h)

### 15.1 Demo video

Follow the PRD section 19 shot list. Length: whatever the Official Rules say, else 2:30.

| Time | Shot |
|---|---|
| 0:00 | Coin drop, "Anting-anting!", sprite glows |
| 0:08 | Friends at the table, no phones |
| 0:20 | Summon split screen: Spark box, SAM mask, Muse Image sprite, model names labeled |
| 0:45 | Voice claim with speaker chips |
| 0:55 | Night: arrows, Taglish orders, chips, End Turn, dodge, tikbalang push |
| 1:35 | Manananggal split, Asin |
| 1:50 | Sunrise and replay reel |
| 2:05 | Architecture, eval numbers, cost per night |
| 2:20 | Title card and repo link |

- Burn in Taglish captions with English subtitles
- Upload as the rules require. Test the link in a private window

### 15.2 README

Use the PRD section 19 outline: GIF, what it is, model table, architecture, setup, how to play, eval results, cost, privacy, limits, credits, license.

Run a secret scan before making the repo public:

```powershell
git log -p | Select-String -Pattern "MODEL_API_KEY|sk-|Bearer "
```

### 15.3 Submit

- Paste the PRD section 19 description, update it with real numbers
- Indie track, Build for Your World
- Name every Meta model used
- Submit by **Nov 4, 11:00 PM SGT** (15:00 UTC, 10:00 AM ET). Hard deadline Nov 5, 10:00 AM SGT
- Save a screenshot of the confirmation

### 15.4 After submitting (Nov 5 to 8)

Post one short clip per day with Taglish captions for the community vote and viral bonus prizes, following any voting rules.

---

## Cut order if a day slips

Cut the first item that saves enough hours. Do it the same day.

| Order | Cut | Saves |
|---|---|---|
| 1 | Duwende steal (becomes a fast weak hitter) | 1 h |
| 2 | Voice claim and overlap (labels show as A, B) | 2 h |
| 3 | Full replay reel (keep a 10 s clip) | 3 h |
| 4 | Diarization (ENDPOINTING plus tap-to-claim) | 1 h |
| 5 | Evals beyond E1 and E7 | 1 h |
| Never cut | Calibration, summon, sprites, tracking, re-anchor, rules, Aswang, Manananggal, Tikbalang push, GM, voice orders, tap, autosave, Demo Safe Mode, cost tracker, video | n/a |

---

## Daily routine

| When | Do |
|---|---|
| Start of day | Read today's row in the schedule. Check credits used |
| Every 2 h | Commit and push |
| End of day | Run pytest. Check the **Done when** line. Note what slipped. Apply the cut order if needed |
| Any blocker over 45 min | Ask in Discord office hours, switch to the next task |

---

## Sources

- Event page: https://cerebralvalley.ai/e/meta-ai-developer-hackathon
- Meta Model API docs: https://dev.meta.ai/docs/overview
- SAM client libraries: https://dev.meta.ai/docs/sam/client-libraries
- SAM segmenting: https://dev.meta.ai/docs/sam/segmenting
- Speech to text: https://dev.meta.ai/docs/speech-to-text
- Image generation: https://dev.meta.ai/docs/image-generation
- Structured output: https://dev.meta.ai/docs/structured-output
- File handling: https://dev.meta.ai/docs/file-handling
- Unofficial notes on the rules (unconfirmed, other teams): https://github.com/meta-ai-hackathon/meta-hack, https://github.com/koushikdatascience-netizen/SentinelX/issues/1
