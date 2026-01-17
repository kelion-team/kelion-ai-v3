# K1 Hologram Functions (Today)

This ZIP contains the **minimum** glue to give your **existing** hologram "life" (state + speaking)
without changing the 3D model/shaders.

## 1) Frontend: load the bridge
Copy `frontend/holo_bridge.js` next to your existing frontend JS and include it **after** the hologram script.

Example:
```html
<script src="/static/js/hologram.js"></script>
<script src="/static/js/holo_bridge.js"></script>
```

Bridge polls `/api/presence` and forwards:
- state: idle | listening | speaking | error
- emotion: neutral | calm | confident | ...
- focus: user | system

It calls these methods **if they exist**:
- window.hologram.setState(state)
- window.hologram.setEmotion(emotion)
- window.hologram.setFocus(focus)
- optional: window.hologram.setSpeaking(true/false)

## 2) Backend: Presence endpoint
If missing, integrate `backend/presence_api.py`:

```py
import sqlite3
from backend.presence_api import register_presence_api

def db_conn():
    conn = sqlite3.connect("data/k1.db")
    conn.row_factory = sqlite3.Row
    return conn

register_presence_api(app, db_conn)
```

## 3) Backend: TTS endpoint (optional stub)
`backend/tts_api.py` is a provider-agnostic stub. If you already have TTS, ignore it.

## 4) Test (real hologram, real animation)
Open your app, DevTools -> Console, paste `tools/force_speaking.js`.
