"""Tratamento do texto: palavras, frases distintas, palavras-chave e trechos (shingles)."""
from __future__ import annotations

import re
import unicodedata

STOP = set((
    "a o as os um uma uns umas de do da dos das em no na nos nas por para com sem sob sobre entre ate ao aos "
    "que se como mais mas ou e ja foi sao ser ter tem seu sua seus suas esse essa esses essas este esta estes estas "
    "isso isto aquele aquela muito muitos pode podem quando onde qual quais cada tambem apos ainda sendo entao assim "
    "ha nao sim the of and to in is that for with as on by an are be this from or at it was"
).split())

_BORDAS = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)


def normalizar_token(palavra: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", palavra) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", sem_acento.lower())


def contar_palavras(texto: str) -> int:
    return len(texto.split())


def tokenizar(texto: str) -> tuple[list[str], list[str]]:
    """Devolve (palavras originais, palavras normalizadas), alinhadas posição a posição."""
    bruto, norm = [], []
    for b in texto.split():
        n = normalizar_token(b)
        if n:
            bruto.append(b)
            norm.append(n)
    return bruto, norm


def normalizar_e_tokenizar(texto: str) -> list[str]:
    """Palavras do texto já normalizadas (minúsculas, sem acento e sem pontuação), na ordem em que aparecem."""
    return tokenizar(texto)[1]


def mapa_shingles(norm: list[str], tam: int) -> dict[str, list[int]]:
    """Trechos de `tam` palavras seguidas -> posições onde começam."""
    mapa: dict[str, list[int]] = {}
    if not norm:
        return mapa
    if len(norm) < tam:
        mapa[" ".join(norm)] = [0]
        return mapa
    for i in range(len(norm) - tam + 1):
        mapa.setdefault(" ".join(norm[i:i + tam]), []).append(i)
    return mapa


def escolher_frases(texto: str, quantidade: int = 5, tam: int = 9) -> list[str]:
    """Escolhe frases espalhadas pelo texto e ricas em palavras incomuns, para procurar na internet."""
    toks = []
    for o in texto.split():
        limpa = _BORDAS.sub("", o).replace('"', "").replace("“", "").replace("”", "")
        if limpa:
            toks.append((limpa, bool(re.search(r"[.!?][\"')\]]*$", o))))
    if len(toks) < tam + 4:
        return []
    frases, usadas = [], set()
    for f in [0.12, 0.3, 0.5, 0.7, 0.88][:quantidade]:
        centro = int(len(toks) * f)
        melhor, melhor_score = None, -1
        for ini in range(max(0, centro - 25), min(len(toks) - tam, centro + 25) + 1):
            janela = toks[ini:ini + tam]
            if any(fim for _, fim in janela[:-1]):
                continue
            score = sum(min(len(p), 10) for p, _ in janela if normalizar_token(p) not in STOP)
            if score > melhor_score:
                melhor_score, melhor = score, janela
        if melhor:
            frase = " ".join(p for p, _ in melhor)
            if frase not in usadas:
                usadas.add(frase)
                frases.append(frase)
    return frases


def palavras_chave(texto: str, n: int = 6) -> list[str]:
    freq: dict[str, int] = {}
    forma: dict[str, str] = {}
    for b in texto.split():
        limpa = _BORDAS.sub("", b).lower()
        norm = normalizar_token(limpa)
        if len(norm) < 5 or any(c.isdigit() for c in norm) or norm in STOP:
            continue
        freq[norm] = freq.get(norm, 0) + 1
        forma.setdefault(norm, limpa)
    ordem = sorted(freq.items(), key=lambda e: (-e[1], -len(e[0])))
    return [forma[k] for k, _ in ordem[:n]]


def palavras_posicionadas(texto: str) -> tuple[list[str], list[str], list[int], list[int]]:
    """Como `tokenizar`, mas também devolve onde cada palavra começa e termina no texto original."""
    bruto, norm, ini, fim = [], [], [], []
    for m in re.finditer(r"\S+", texto):
        n = normalizar_token(m.group())
        if n:
            bruto.append(m.group())
            norm.append(n)
            ini.append(m.start())
            fim.append(m.end())
    return bruto, norm, ini, fim
