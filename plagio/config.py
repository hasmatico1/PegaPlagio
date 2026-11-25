"""Configurações do usuário, guardadas numa pasta do próprio usuário (a chave não fica dentro do programa)."""
from __future__ import annotations

import json
import os
from pathlib import Path

CAMINHO = Path.home() / ".pega_plagio" / "config.json"
PADRAO = {"openalex_chave": "", "conferir_referencias": True}


def carregar() -> dict:
    cfg = dict(PADRAO)
    try:
        dados = json.loads(CAMINHO.read_text(encoding="utf-8"))
        if isinstance(dados, dict):
            cfg.update({k: dados[k] for k in PADRAO if k in dados})
    except (OSError, ValueError):
        pass
    if not str(cfg["openalex_chave"]).strip():
        cfg["openalex_chave"] = os.environ.get("OPENALEX_API_KEY", "").strip()
    cfg["openalex_chave"] = str(cfg["openalex_chave"]).strip()
    cfg["conferir_referencias"] = bool(cfg["conferir_referencias"])
    return cfg


def salvar(cfg: dict) -> None:
    CAMINHO.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO.write_text(json.dumps({k: cfg.get(k, PADRAO[k]) for k in PADRAO}, ensure_ascii=False, indent=2),
                       encoding="utf-8")
