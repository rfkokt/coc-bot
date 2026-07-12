#!/usr/bin/env python3
"""Config untuk Deep Research — LLM endpoint + SearXNG. Stdlib only.

Settings disimpan di research_config.json (di-gitignore). Fallback ke env var.
Struktur ngikutin pola Odysseus: OpenAI-compatible LLM endpoint + SearXNG search.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "research_config.json")

DEFAULTS = {
    # OpenAI-compatible LLM endpoint. Base URL saja (tanpa /chat/completions).
    # Contoh: http://localhost:1234/v1 (LM Studio), http://localhost:11434/v1 (Ollama),
    #         https://openrouter.ai/api/v1, https://api.openai.com/v1
    "llm_base_url": os.getenv("RESEARCH_LLM_URL", "http://localhost:1234/v1"),
    "llm_api_key": os.getenv("RESEARCH_LLM_KEY", ""),
    "llm_model": os.getenv("RESEARCH_LLM_MODEL", ""),
    # SearXNG instance (JSON API harus aktif — set `formats: [html, json]` di settings.yml)
    "searxng_url": os.getenv("RESEARCH_SEARXNG_URL", "http://localhost:8080"),
    "searxng_engines": os.getenv("RESEARCH_SEARXNG_ENGINES", "google,mojeek,presearch"),
    # Berapa ronde iterasi max (0 = auto, capped 6)
    "max_rounds": int(os.getenv("RESEARCH_MAX_ROUNDS", "3")),
    # Berapa URL di-fetch per ronde
    "max_urls_per_round": 3,
    # Budget waktu total (detik)
    "max_time": 300,
}


def load_config() -> dict:
    """Load config, merge dengan defaults."""
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH) as f:
            saved = json.load(f)
            cfg.update({k: v for k, v in saved.items() if v is not None})
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return cfg


def save_config(updates: dict) -> dict:
    """Merge updates ke config yang ada, simpan ke disk. Return config terbaru."""
    cfg = {}
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    # Whitelist field yang boleh di-set dari UI
    allowed = {"llm_base_url", "llm_api_key", "llm_model", "searxng_url", "searxng_engines",
               "max_rounds", "max_urls_per_round", "max_time"}
    for k, v in updates.items():
        if k in allowed:
            cfg[k] = v
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    return load_config()


def public_config() -> dict:
    """Config untuk dikirim ke UI — API key di-mask."""
    cfg = load_config()
    key = cfg.get("llm_api_key", "")
    return {
        **cfg,
        "llm_api_key": ("••••" + key[-4:]) if len(key) > 4 else ("••••" if key else ""),
        "llm_api_key_set": bool(key),
    }
