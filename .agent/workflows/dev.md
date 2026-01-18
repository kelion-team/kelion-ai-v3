---
description: Development workflow for KELION_FRONTEND - runs all commands automatically
---

// turbo-all

## ⚠️ OBLIGATORIU - CITEȘTE ÎNTÂI

0. **CITEȘTE AI_SESSION_NOTES.md** înainte de ORICE altceva!
```bash
type AI_SESSION_NOTES.md
```
> Conține regulile critice ale proiectului:
> - USE ONLY GIT - fără modificări locale
> - GitHub → Railway (auto-deploy)
> - NOTIFY BEFORE ANY CODE CHANGES

---

## Development Commands

1. Install dependencies
```bash
pip install -r requirements.txt
```

2. Run the development server
```bash
python app.py
```

3. Check server status
```bash
curl http://localhost:8080
```

4. View logs
```bash
type logs\*.log
```

## Build & Deploy

5. Build static assets
```bash
npm run build
```

6. Run tests
```bash
pytest
```

## File Operations

7. List project structure
```bash
dir /s /b
```

8. Check git status
```bash
git status
```
