"""Avalia se o trabalho tem referências adequadas.

Confere, sem IA e sem internet, aspectos formais baseados nas normas ABNT (NBR 6023 e NBR 10520):
  - existe uma seção de referências?
  - as referências estão no formato esperado (autor, título, ano...)?
  - o texto tem citações do tipo (SOBRENOME, 2020) ou Sobrenome (2020)?
  - toda citação aparece na lista de referências, e toda referência é citada no texto?
  - citações diretas longas (entre aspas) trazem a fonte?

É uma conferência de forma. Ela não verifica se o conteúdo citado está correto.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .texto import normalizar_token

MAI = "A-ZÀ-ÖØ-Ý"
MIN = "a-zà-öø-ÿ"

CABECALHO = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*[\s.\-–]*)?(?:refer[eê]ncias(?:\s+bibliogr[aá]ficas)?|bibliografia|obras\s+consultadas|references)\s*:?\s*$",
    re.I)
FIM_SECAO = re.compile(r"^\s*(?:anexos?|ap[eê]ndices?|gloss[aá]rio)\b", re.I)
INICIO_ENTRADA = re.compile(
    rf"^\s*(?:\[\d+\]|\d+[.)])?\s*(?:[{MAI}][{MAI}'’\-]+(?:\s+[{MAI}'’\-]+){{0,5}},\s+\S|[{MAI}][{MAI}]+(?:\s+[{MAI}]+){{0,6}}\.\s+\S)")
NUMERACAO = re.compile(r"^\s*(?:\[\d+\]|\d+[.)])\s*")
ANO = re.compile(r"\b(1[5-9]\d{2}|20\d{2})[a-z]?\b")
URL = re.compile(r"https?://|www\.", re.I)
ACESSO = re.compile(r"acesso\s+em", re.I)

PAREN = re.compile(r"\(([^()]{3,250})\)")
MAIUSCULA = re.compile(rf"[{MAI}][A-Za-zÀ-ÿ'’\-]+")
NARRATIVA = re.compile(
    rf"([{MAI}][{MIN}'’\-]{{1,}})(?:\s+(?:et\s+al\.?|e\s+[{MAI}][{MIN}'’\-]+))?\s*\((\d{{4}})[a-z]?(?:[,\s][^)]*)?\)")
NUMERICA = re.compile(r"\[(\d+(?:\s*[,\-–]\s*\d+)*)\]")
ASPAS = re.compile(r"[“\"]([^”\"]{90,}?)[”\"]")
NAO_AUTOR = {"figura", "tabela", "quadro", "grafico", "fonte", "elaboracao", "anexo", "apendice", "cap", "capitulo",
             "secao", "item", "ver", "vide", "apud", "cf", "et", "al", "em", "no", "na", "de", "do", "ate", "desde",
             "ano", "conforme", "segundo", "idem", "ibidem", "p", "pp"}


@dataclass
class Entrada:
    texto: str
    sobrenome: str = ""
    sobrenomes: list[str] = field(default_factory=list)   # todos os autores da referência
    ano: str = ""
    titulo: str | None = None
    problemas: list[str] = field(default_factory=list)


@dataclass
class Item:
    status: str   # "ok", "atencao" ou "problema"
    texto: str


@dataclass
class AnaliseReferencias:
    tem_secao: bool = False
    entradas: list[Entrada] = field(default_factory=list)
    citacoes: list[tuple[str, str, str]] = field(default_factory=list)   # (sobrenome para exibir, ano, chave)
    citadas_sem_referencia: list[str] = field(default_factory=list)
    referencias_sem_citacao: list[Entrada] = field(default_factory=list)
    aspas_sem_fonte: list[str] = field(default_factory=list)
    palavras_sem_referencia: int = 0      # palavras em trechos com citação sem referência na lista
    pct_sem_referencia: float = 0.0       # o mesmo, em % das palavras do trabalho
    estilo_numerico: bool = False
    itens: list[Item] = field(default_factory=list)
    veredito: str = "inadequado"   # "adequado", "parcial" ou "inadequado"
    palavras_corpo: int = 0


# ---------------------------------------------------------------------------
def _linhas(texto: str) -> list[tuple[int, int, str]]:
    """(início, fim, conteúdo) de cada linha. Separa só por \\n, para as posições baterem com o texto."""
    return [(m.start(), m.end(), m.group().rstrip("\n")) for m in re.finditer(r"[^\n]*\n|[^\n]+$", texto)]


def _achar_secao(texto: str) -> tuple[int, int, int] | None:
    """(início do título, fim do título, fim da seção) da seção de referências, se existir."""
    linhas = _linhas(texto)
    candidatos = [i for i, (_, _, l) in enumerate(linhas) if CABECALHO.match(l)]
    for i in reversed(candidatos):
        fim_bloco, n = len(texto), 0
        for ini, _, l in linhas[i + 1:]:
            if FIM_SECAO.match(l):
                fim_bloco = ini
                break
            n += bool(l.strip())
        if n >= 2:
            return linhas[i][0], linhas[i][1], fim_bloco
    if candidatos:
        i = candidatos[-1]
        return linhas[i][0], linhas[i][1], linhas[i][1]
    return None


def separar_secao(texto: str) -> tuple[str, str, bool]:
    achou = _achar_secao(texto)
    if achou is None:
        return texto, "", False
    ini, fim, fim_bloco = achou
    return texto[:ini], texto[fim:fim_bloco], True


def inicio_secao(texto: str) -> int | None:
    """Posição, no texto, onde começa a seção de referências (None se não houver)."""
    achou = _achar_secao(texto)
    return achou[0] if achou else None


def dividir_entradas(bloco: str) -> list[str]:
    entradas: list[str] = []
    atual: list[str] = []

    def fechar():
        if atual:
            entradas.append(" ".join(atual).strip())
            atual.clear()

    for linha in bloco.splitlines():
        if not linha.strip():
            fechar()
        elif INICIO_ENTRADA.match(linha):
            fechar()
            atual.append(linha.strip())
        else:
            atual.append(linha.strip())
    fechar()
    return [e for e in entradas if e]


def analisar_entrada(bruto: str) -> Entrada:
    t = NUMERACAO.sub("", bruto).strip()
    e = Entrada(texto=bruto)
    padrao_ok = bool(INICIO_ENTRADA.match(t))
    m = re.match(r"^\s*([^,.;]+)", t)
    if m:
        palavras = m.group(1).split()
        e.sobrenome = normalizar_token(palavras[0]) if palavras else ""
    sem_acesso = ACESSO.split(t)[0]
    anos = ANO.findall(sem_acesso)
    if anos:
        e.ano = re.findall(r"\b(?:1[5-9]\d{2}|20\d{2})", sem_acesso)[-1]
    partes = re.split(r"\.\s+", t)
    i = 1
    while i < len(partes) and (len(partes[i]) <= 3 or partes[i].lower().rstrip(".") == "et al"):
        i += 1
    if i < len(partes):
        titulo = re.sub(r"^(?:In|IN)\s*:\s*", "", partes[i]).strip(" .:;")
        e.titulo = titulo if len(titulo) >= 6 else None
    antes = t[:t.find(e.titulo)] if e.titulo and e.titulo in t else t[:120]
    nomes = re.findall(rf"([{MAI}][{MAI}'’\-]+)(?:\s+[{MAI}'’\-]+)*,\s", antes)
    e.sobrenomes = list(dict.fromkeys(normalizar_token(n) for n in nomes if normalizar_token(n)))
    if e.sobrenome and e.sobrenome not in e.sobrenomes:
        e.sobrenomes.insert(0, e.sobrenome)
    if not e.ano:
        e.problemas.append("não informa o ano de publicação")
    if not padrao_ok:
        e.problemas.append("autor fora do padrão ABNT (SOBRENOME, Nome)")
    if not e.titulo:
        e.problemas.append("título não identificado")
    if URL.search(t) and not ACESSO.search(t):
        e.problemas.append('endereço da internet sem a data de acesso ("Acesso em: dia mês ano")')
    if len(t) < 30:
        e.problemas.append("referência muito curta, parece incompleta")
    return e


# ---------------------------------------------------------------------------
def _citacoes_autor_ano(corpo: str) -> list[tuple[str, str, str, bool, int]]:
    """(sobrenome para exibir, ano, chave, exige_referencia, posição no texto)"""
    achadas: list[tuple[str, str, str, bool, int]] = []
    for m in PAREN.finditer(corpo):
        conteudo = m.group(1)
        if not ANO.search(conteudo):
            continue
        partes_apud = re.split(r"\bapud\b", conteudo, flags=re.I)
        for idx, trecho in enumerate(partes_apud):
            exige = idx == len(partes_apud) - 1       # na citação "apud" só a fonte consultada vai para a lista
            pendentes: list[str] = []
            for pedaco in trecho.split(";"):
                nome = next((x for x in MAIUSCULA.findall(pedaco) if normalizar_token(x) not in NAO_AUTOR), None)
                ano = ANO.search(pedaco)
                if nome is None:
                    continue
                if ano:
                    a = re.match(r"\d{4}", ano.group(0)).group(0)
                    for n in pendentes + [nome]:
                        achadas.append((n, a, f"{normalizar_token(n)}|{a}", exige, m.start()))
                    pendentes = []
                else:
                    pendentes.append(nome)
    for m in NARRATIVA.finditer(corpo):
        nome = m.group(1)
        if normalizar_token(nome) in NAO_AUTOR:
            continue
        achadas.append((nome, m.group(2), f"{normalizar_token(nome)}|{m.group(2)}", True, m.start()))
    return achadas


def _classificar_aspas(corpo: str) -> tuple[list[tuple[str, int, int]], list[tuple[int, int]]]:
    """Separa as citações diretas longas (entre aspas) em: sem fonte e com fonte indicada."""
    sem_fonte, com_fonte = [], []
    for m in ASPAS.finditer(corpo):
        depois = corpo[m.end():m.end() + 60]
        antes = re.sub(r"\bpp?\.\s", "p ", corpo[max(0, m.start() - 120):m.start()])
        antes_da_frase = re.split(r"[.!?]\s", antes)[-1]
        if (re.match(r"^[\s.,;:)]{0,4}(\([^)]*\d{4}[^)]*\)|\[\d+)", depois)
                or re.match(r"^[\s.,;:)]{0,4}\(?apud\b", depois, re.I) or NARRATIVA.search(antes_da_frase)):
            com_fonte.append((m.start(), m.end()))
        else:
            sem_fonte.append((m.group(1).strip()[:90] + "...", m.start(), m.end()))
    return sem_fonte, com_fonte


def spans_aspas_com_fonte(corpo: str) -> list[tuple[int, int]]:
    """Trechos entre aspas que indicam a fonte: são citação correta, não plágio."""
    return _classificar_aspas(corpo)[1]


def _sentencas(corpo: str) -> list[tuple[int, int]]:
    mascara = re.sub(r"\b(p|pp|v|n|cap|fig|ed|vol|et al|apud|ex|dr|dra|prof|sr|sra)\.",
                     lambda m: m.group()[:-1] + "·", corpo, flags=re.I)
    spans, ini = [], 0
    for m in re.finditer(r"[.!?]+[\"”')\]]*(?=\s)|\n\s*\n", mascara):
        spans.append((ini, m.end()))
        ini = m.end()
    if ini < len(corpo):
        spans.append((ini, len(corpo)))
    return spans


def _palavras_em(corpo: str, trechos: list[tuple[int, int]]) -> tuple[int, int]:
    """(palavras do corpo dentro dos trechos, total de palavras do corpo)"""
    inicios = [m.start() for m in re.finditer(r"\S+", corpo)]
    dentro = sum(1 for p in inicios if any(a <= p < b for a, b in trechos))
    return dentro, len(inicios)


def analisar_referencias(texto: str) -> AnaliseReferencias:
    corpo, bloco, tem = separar_secao(texto)
    r = AnaliseReferencias(tem_secao=tem, palavras_corpo=len(corpo.split()))
    r.entradas = [analisar_entrada(e) for e in dividir_entradas(bloco)]

    brutas = _citacoes_autor_ano(corpo)
    numericas = NUMERICA.findall(corpo)
    r.estilo_numerico = bool(numericas) and not brutas
    vistos: set[str] = set()
    for nome, ano, chave, _, _p in brutas:
        if chave not in vistos:
            vistos.add(chave)
            r.citacoes.append((nome, ano, chave))

    chaves_refs = {f"{s}|{e.ano}" for e in r.entradas if e.ano for s in e.sobrenomes}
    exigidas = {c for _, _, c, exige, _p in brutas if exige}
    nome_por_chave = {c: f"{n} ({a})" for n, a, c in r.citacoes}
    if not r.estilo_numerico:
        r.citadas_sem_referencia = sorted(nome_por_chave[c] for c in exigidas if c not in chaves_refs)
        citadas = {c for _, _, c in r.citacoes}
        r.referencias_sem_citacao = [e for e in r.entradas
                                     if e.sobrenomes and e.ano and not any(f"{s}|{e.ano}" in citadas for s in e.sobrenomes)]
    sem_fonte, _ = _classificar_aspas(corpo)
    r.aspas_sem_fonte = [t for t, _, _ in sem_fonte]

    # quanto do trabalho está em trechos com citação sem referência (ou citação direta sem fonte)
    sentencas = _sentencas(corpo)
    suspeitas = [(a, b) for a, b in ((x[1], x[2]) for x in sem_fonte)]
    pos_orfas = []
    if r.estilo_numerico:
        for m in NUMERICA.finditer(corpo):
            if any(int(x) > len(r.entradas) for x in re.findall(r"\d+", m.group(1))):
                pos_orfas.append(m.start())
    else:
        pos_orfas = [p for _, _, c, exige, p in brutas if exige and c not in chaves_refs]
    for p in pos_orfas:
        suspeitas += [(a, b) for a, b in sentencas if a <= p < b]
    r.palavras_sem_referencia, total = _palavras_em(corpo, suspeitas)
    r.pct_sem_referencia = 100.0 * r.palavras_sem_referencia / total if total else 0.0

    # ---------------- lista de verificação e veredito ----------------
    it = r.itens
    n = len(r.entradas)
    if not tem:
        it.append(Item("problema", 'O trabalho não tem uma seção de referências (um título "Referências" ou "Bibliografia").'))
    elif n == 0:
        it.append(Item("problema", "A seção de referências existe, mas não foi possível identificar nenhuma referência nela."))
    else:
        it.append(Item("ok", f"Seção de referências encontrada, com {n} referência(s)."))

    ncit = len(numericas) if r.estilo_numerico else len(r.citacoes)
    if ncit == 0 and r.palavras_corpo >= 300:
        it.append(Item("problema", "O texto não traz nenhuma citação. Exemplos aceitos: (SILVA, 2020), Silva (2020) ou [1]."))
    elif ncit > 0:
        estilo = "numéricas" if r.estilo_numerico else "de autor e data"
        it.append(Item("ok", f"{ncit} citação(ões) {estilo} no texto."))

    if r.estilo_numerico and n and numericas:
        maior = max(int(x) for grupo in numericas for x in re.findall(r"\d+", grupo))
        if maior > n:
            it.append(Item("problema", f"Há citação numérica [{maior}], mas a lista só tem {n} referência(s)."))

    if r.citadas_sem_referencia:
        lista = ", ".join(r.citadas_sem_referencia[:6]) + ("..." if len(r.citadas_sem_referencia) > 6 else "")
        it.append(Item("problema", f"{len(r.citadas_sem_referencia)} citação(ões) do texto não aparece(m) na lista de referências: {lista}."))
    elif tem and n and r.citacoes and not r.estilo_numerico:
        it.append(Item("ok", "Todas as citações do texto aparecem na lista de referências."))

    if r.referencias_sem_citacao:
        it.append(Item("atencao", f"{len(r.referencias_sem_citacao)} referência(s) da lista não é(são) citada(s) no texto. "
                                   "Pela ABNT, a lista deve conter apenas obras citadas."))

    com_problema = [e for e in r.entradas if e.problemas]
    if com_problema:
        gravidade = "problema" if n and len(com_problema) / n > 0.5 else "atencao"
        it.append(Item(gravidade, f"{len(com_problema)} de {n} referência(s) têm problemas de formato (veja a lista abaixo)."))
    elif n:
        it.append(Item("ok", "Todas as referências seguem o formato esperado."))

    if r.aspas_sem_fonte:
        it.append(Item("problema", f"{len(r.aspas_sem_fonte)} citação(ões) direta(s) longa(s), entre aspas, sem indicar a fonte."))

    problemas = sum(1 for i in it if i.status == "problema")
    atencoes = sum(1 for i in it if i.status == "atencao")
    sem_citacao = ncit == 0 and r.palavras_corpo >= 300
    muitas_orfas = bool(r.citacoes) and len(r.citadas_sem_referencia) >= 0.5 * len(r.citacoes)
    if not tem or n == 0 or sem_citacao or muitas_orfas:
        r.veredito = "inadequado"
    elif problemas == 0 and atencoes <= 1:
        r.veredito = "adequado"
    else:
        r.veredito = "parcial"
    return r
