## AGENTS.md

### 🚀 Quickstart
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pip install -r requirements.txt
python3 stress_test.py --jobs 9 --concurrency 3 --api-key <key>
```

### 📁 Structure
```
apia/
├── main.py
├── requirements.txt
├── app/
│   ├── config.py
│   ├── models.py
│   ├── router.py
│   ├── core/
│   │   ├── auth.py
│   │   ├── database.py
│   │   ├── scheduler.py
│   │   └── model_registry.py
│   └── services/
│       ├── base.py
│       ├── translation.py
│       ├── product_qa.py
│       └── commercial_text.py
└── tests/
    └── stress_test.py
```

### ⚙️ Architecture
- **Flow**: POST /api/* → enqueue() → ModelAwareScheduler → worker()
- **Key Modules**: `ModelAwareScheduler` (min-heap model prioritization), `BaseService` (model-agnostic execution), `model_registry.py` (code/text model tagging)

### 🔐 Security
- API keys hashed with SHA-256 in `api_keys` table
- Admin secrets in `ADMIN_SECRET` env var
- Never store plain text secrets

### 📦 Setup
1. `uvicorn` for dev server
2. `aiomysql` pool in `database.py`
3. `secrets.token_hex(32)` for new API keys

### ⚠️ Gotchas
- **Single Ollama worker** to prevent GPU saturation
- `llama3.2:3b` is default (VRAM-friendly)
- `num_predict` varies by service: translation (200), product_qa (200), commercial_text (300)
- Stress tests require valid API keys

### 📄 Documentation
- `AGENTS.md` summarizes the project's architecture and conventions