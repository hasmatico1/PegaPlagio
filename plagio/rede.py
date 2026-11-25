"""Conexão com a internet: detecção de conexão e requisições simples (sem IA, sem chave)."""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

# Servidores usados na busca. Se nenhum responder, o programa considera que não há internet.
HOSTS_TESTE: list[tuple[str, int]] = [("api.openalex.org", 443), ("pt.wikipedia.org", 443)]
USER_AGENT = "PegaPlagio/1.0 (programa de computador; uso academico)"


class ErroRede(Exception):
    """codigo: 'rede' (sem conexão), 'limite' (muitas consultas), 'chave' (chave recusada) ou 'http'."""

    def __init__(self, codigo: str):
        super().__init__(codigo)
        self.codigo = codigo


def tem_internet(timeout: float = 3.0) -> bool:
    for host, porta in HOSTS_TESTE:
        try:
            with socket.create_connection((host, porta), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def obter_json(url: str, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ErroRede("limite" if e.code in (402, 409, 429) else "chave" if e.code in (401, 403) else "http") from e
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
        raise ErroRede("rede") from e
    except ValueError as e:
        raise ErroRede("http") from e


def baixar_bytes(url: str, limite: int = 15_000_000, timeout: float = 25.0) -> bytes:
    """Baixa um PDF (só aceita http/https e PDF, até `limite` bytes)."""
    if not url.lower().startswith(("http://", "https://")):
        raise ErroRede("http")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            tipo = (resp.headers.get("Content-Type") or "").lower()
            if "pdf" not in tipo and not url.lower().split("?")[0].endswith(".pdf"):
                raise ErroRede("http")
            partes, total = [], 0
            while True:
                bloco = resp.read(65536)
                if not bloco:
                    break
                total += len(bloco)
                if total > limite:
                    raise ErroRede("http")
                partes.append(bloco)
            return b"".join(partes)
    except urllib.error.HTTPError as e:
        raise ErroRede("limite" if e.code == 429 else "http") from e
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
        raise ErroRede("rede") from e
