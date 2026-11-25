"""Comparação do trabalho com arquivos que o próprio usuário fornece (colegas, fontes que ele juntou)."""
from __future__ import annotations

from dataclasses import dataclass

from .texto import mapa_shingles, tokenizar

TAM = 5
PESO_CARACTERES = 0.5   # na similaridade híbrida: 50% semelhança de caracteres, 50% de palavras


@dataclass
class ResultadoLocal:
    nome: str
    cobertura: float      # % do texto do usuário que aparece no arquivo comparado
    jaccard: float        # % de semelhança geral
    risco: str            # "baixo", "medio", "alto" ou "critico"
    trechos: list[str]
    palavras: list[str]   # palavras do texto do usuário, na ordem original
    marcado: list[bool]   # para cada palavra: faz parte de um trecho igual?


def classificar(cobertura_pct: float) -> str:
    if cobertura_pct >= 60:
        return "critico"
    if cobertura_pct >= 35:
        return "alto"
    if cobertura_pct >= 15:
        return "medio"
    return "baixo"


def comparar(texto: str, nome: str, texto_ref: str) -> ResultadoLocal:
    brutas, norm_a = tokenizar(texto)
    mapa_a = mapa_shingles(norm_a, TAM)
    mapa_r = mapa_shingles(tokenizar(texto_ref)[1], TAM)
    comuns = [s for s in mapa_a if s in mapa_r]
    uniao = len(mapa_a) + len(mapa_r) - len(comuns)
    cob = 100.0 * len(comuns) / len(mapa_a) if mapa_a else 0.0
    jac = 100.0 * len(comuns) / uniao if uniao else 0.0
    marcado = [False] * len(brutas)
    for s in comuns:
        for ini in mapa_a[s]:
            for k in range(TAM):
                if ini + k < len(marcado):
                    marcado[ini + k] = True
    comuns.sort(key=len, reverse=True)
    return ResultadoLocal(nome, cob, jac, classificar(cob), comuns[:8], brutas, marcado)


def distancia_levenshtein(a: str, b: str) -> int:
    """Menor número de inserções, remoções ou trocas de um caractere para transformar `a` em `b`.

    Usa o algoritmo de Myers (1999), na versão de Hyyrö: calcula exatamente o mesmo número da tabela
    tradicional, mas processa os caracteres em blocos de bits. Isso o deixa muito mais rápido e leve em textos
    longos (a tabela tradicional ocupa memória e tempo proporcionais ao tamanho de um texto vezes o do outro).
    """
    if a == b:
        return 0
    if len(a) > len(b):
        a, b = b, a                      # `a` (o menor) vira o padrão; os bits representam as posições dele
    if not a:
        return len(b)
    m = len(a)
    tudo = (1 << m) - 1
    ultimo = 1 << (m - 1)
    posicoes: dict[str, int] = {}
    for i, ch in enumerate(a):
        posicoes[ch] = posicoes.get(ch, 0) | (1 << i)
    pv, mv, dist = tudo, 0, m
    for ch in b:
        eq = posicoes.get(ch, 0)
        xv = eq | mv
        xh = ((((eq & pv) + pv) ^ pv) | eq) & tudo
        ph = (mv | (~(xh | pv) & tudo)) & tudo
        mh = pv & xh
        if ph & ultimo:
            dist += 1
        elif mh & ultimo:
            dist -= 1
        ph = ((ph << 1) | 1) & tudo
        mh = (mh << 1) & tudo
        pv = (mh | (~(xv | ph) & tudo)) & tudo
        mv = ph & xv
    return dist


def calcular_similaridade_hibrida(texto_a: str, texto_b: str, tokens_a: list[str], tokens_b: list[str]) -> float:
    """Similaridade de 0 a 1 que junta duas visões do mesmo par de textos:
      - de caracteres: 1 - (distância de Levenshtein / tamanho do maior texto). Pega pequenas trocas, como
        "software" e "softwares", que contam como pouca diferença;
      - de palavras: parte das palavras diferentes que os dois textos têm em comum (índice de Jaccard).
    O resultado é a média ponderada das duas (PESO_CARACTERES para a de caracteres, o resto para a de palavras).
    """
    maior = max(len(texto_a), len(texto_b))
    if maior == 0:
        return 0.0
    sim_caracteres = 1.0 - distancia_levenshtein(texto_a, texto_b) / maior
    a, b = set(tokens_a), set(tokens_b)
    sim_palavras = len(a & b) / len(a | b) if (a or b) else 0.0
    return PESO_CARACTERES * sim_caracteres + (1.0 - PESO_CARACTERES) * sim_palavras
