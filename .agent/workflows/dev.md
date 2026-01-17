---
description: Development workflow for KELION_FRONTEND - runs all commands automatically
---

// turbo-all

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
