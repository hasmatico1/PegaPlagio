"""Busca de trabalhos parecidos na internet, sem IA: catálogo acadêmico OpenAlex e Wikipédia."""
from __future__ import annotations

import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Callable

from .leitor import ler_pdf_bytes
from .rede import ErroRede, baixar_bytes, obter_json
from .referencias import inicio_secao, spans_aspas_com_fonte
from .texto import (STOP, escolher_frases, mapa_shingles, normalizar_token, palavras_chave, palavras_posicionadas,
                    tokenizar)

URL_OPENALEX = "https://api.openalex.org/works"
URL_WIKIPEDIA = "https://pt.wikipedia.org/w/api.php"
URL_PAGINA_WIKIPEDIA = "https://pt.wikipedia.org/wiki/"
CAMPOS = "id,display_name,publication_year,doi,type,authorships,abstract_inverted_index,primary_location,best_oa_location"
TAM_FONTE = 6        # palavras seguidas iguais para considerar um trecho copiado
LACUNA = 2           # palavras diferentes toleradas no meio de um trecho copiado (pequenas trocas)
MAX_FONTES = 6       # quantas fontes têm o texto baixado para comparação
PAUSA = 0.3  # segundos entre consultas, para não sobrecarregar os serviços
CHAVE_OPENALEX = ""   # chave gratuita do OpenAlex (opcional): aumenta bastante o limite diário de buscas

TIPOS = {"article": "Artigo", "dissertation": "Dissertação ou tese", "book": "Livro",
         "book-chapter": "Capítulo de livro", "preprint": "Preprint", "review": "Revisão", "report": "Relatório"}

Progresso = Callable[[float, str], None]


@dataclass
class Achado:
    titulo: str
    autores: str
    ano: str
    tipo: str
    link: str
    fonte: str                       # "OpenAlex" ou "Wikipédia"
    frases: list[str] = field(default_factory=list)
    cobertura: float = 0.0           # parte do resumo do trabalho que aparece no texto enviado (0 a 1)
    nivel: str = "tema"              # "alto", "medio" ou "tema"
    resumo: str = ""
    pdf_url: str = ""
    chave_fonte: str = ""            # título da página (Wikipédia), usado para baixar o texto
    texto_fonte: str = ""            # texto usado na comparação
    origem_texto: str = ""           # "completo" ou "resumo"
    palavras: int = 0                # palavras do trabalho que vieram desta fonte
    pct: float = 0.0                 # o mesmo, em % do trabalho
    marcas_fonte: list[tuple[int, int]] = field(default_factory=list)   # trechos copiados, dentro de texto_fonte


@dataclass
class Trecho:
    """Um pedaço do trabalho enviado que foi copiado de uma fonte."""
    ini: int                          # posição no texto enviado (caractere)
    fim: int
    fonte: int                        # índice da fonte em ResultadoBusca.achados
    palavras: int
    palavra_ini: int = 0              # primeira e última palavra do trecho, no trabalho enviado
    palavra_fim: int = 0
    fonte_ini: int = -1               # onde esse mesmo trecho está no texto da fonte (caractere); -1 se não se sabe
    fonte_fim: int = -1


@dataclass
class ResultadoBusca:
    achados: list[Achado]
    limite: bool
    falhas: int
    sucessos: int
    frases: list[str]
    trechos: list[Trecho] = field(default_factory=list)
    plagio_pct: float = 0.0           # % do trabalho copiado (mínimo comprovado)
    palavras_plagiadas: int = 0
    palavras_corpo: int = 0
    palavras_citadas_ok: int = 0      # copiadas, mas entre aspas e com a fonte indicada: não contam como plágio
    parcial: bool = False             # alguma fonte só foi comparada pelo resumo/trechos, não pelo texto inteiro
    erro_chave: bool = False          # o OpenAlex recusou a chave informada


def definir_chave(chave: str) -> None:
    global CHAVE_OPENALEX
    CHAVE_OPENALEX = (chave or "").strip()


def testar_chave(chave: str) -> None:
    """Faz uma busca de teste com a chave informada. Lança ErroRede ('chave', 'limite' ou 'rede') se não funcionar."""
    anterior = CHAVE_OPENALEX
    definir_chave(chave)
    try:
        _openalex("pesquisa")
    finally:
        definir_chave(anterior)


def _openalex(consulta: str) -> list[dict]:
    params = {"search": consulta, "per-page": 8, "select": CAMPOS}
    if CHAVE_OPENALEX:
        params["api_key"] = CHAVE_OPENALEX
    return obter_json(URL_OPENALEX + "?" + urllib.parse.urlencode(params)).get("results", []) or []


def _json_wikipedia(url: str) -> dict:
    try:
        return obter_json(url)
    except ErroRede as e:
        raise ErroRede("http" if e.codigo == "chave" else e.codigo) from e   # a Wikipédia não usa a chave do OpenAlex


def _wikipedia(frase: str) -> list[dict]:
    url = URL_WIKIPEDIA + "?" + urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": f'"{frase}"', "srlimit": 5,
        "srnamespace": 0, "srprop": "snippet", "format": "json"})
    return (_json_wikipedia(url).get("query", {}) or {}).get("search", []) or []


def _resumo(indice: dict | None) -> str:
    if not indice:
        return ""
    pos: dict[int, str] = {}
    for palavra, lugares in indice.items():
        for p in lugares:
            pos[p] = palavra
    return " ".join(pos[k] for k in sorted(pos))


def _autores(obra: dict) -> str:
    nomes = [(a.get("author") or {}).get("display_name") for a in obra.get("authorships") or []]
    nomes = [n for n in nomes if n]
    if not nomes:
        return "Autoria não informada"
    return ", ".join(nomes[:3]) + (" e outros" if len(nomes) > 3 else "")


def _link(obra: dict) -> str:
    loc = obra.get("primary_location") or {}
    return loc.get("landing_page_url") or obra.get("doi") or obra.get("id") or ""


def _pdf_url(o: dict) -> str:
    return ((o.get("best_oa_location") or {}).get("pdf_url") or (o.get("primary_location") or {}).get("pdf_url") or "")


def _novo(o: dict) -> Achado:
    return Achado(o.get("display_name") or "Sem título", _autores(o), str(o.get("publication_year") or ""),
                  TIPOS.get(o.get("type"), "Trabalho"), _link(o), "OpenAlex",
                  resumo=_resumo(o.get("abstract_inverted_index")), pdf_url=_pdf_url(o))


def _wikipedia_texto(titulo: str) -> str:
    url = URL_WIKIPEDIA + "?" + urllib.parse.urlencode({
        "action": "query", "prop": "extracts", "explaintext": 1, "exlimit": 1, "redirects": 1,
        "titles": titulo, "format": "json"})
    paginas = (_json_wikipedia(url).get("query") or {}).get("pages") or {}
    for p in paginas.values():
        return p.get("extract") or ""
    return ""


def _marcar_plagio(texto: str, achados: list[Achado]) -> tuple[list[Trecho], int, int, int]:
    """Compara o trabalho com o texto de cada fonte. Devolve (trechos, palavras do corpo, plagiadas, citadas ok)."""
    brutas, norm, ini, fim = palavras_posicionadas(texto)
    corte = inicio_secao(texto)
    corpo_txt = texto if corte is None else texto[:corte]
    n = len(norm) if corte is None else sum(1 for x in ini if x < corte)   # a lista de referências não conta
    norm = norm[:n]
    citados = spans_aspas_com_fonte(corpo_txt)
    citada_ok = [any(a <= ini[i] < b for a, b in citados) for i in range(n)]

    mapas: dict[int, dict[str, list[int]]] = {}

    def mapa(tam: int) -> dict[str, list[int]]:
        if tam not in mapas:
            mapas[tam] = mapa_shingles(norm, tam)
        return mapas[tam]

    marcadas: list[set[int]] = []
    for a in achados:
        m: set[int] = set()
        if a.texto_fonte:
            fonte = set(mapa_shingles(tokenizar(a.texto_fonte)[1], TAM_FONTE))
            for sh, posicoes in mapa(TAM_FONTE).items():
                if sh in fonte:
                    for p in posicoes:
                        m.update(range(p, p + TAM_FONTE))
        for f in a.frases:                                    # as frases que levaram à descoberta sempre aparecem
            fn = tokenizar(f)[1]
            for p in mapa(len(fn)).get(" ".join(fn), []):
                m.update(range(p, p + len(fn)))
        marcadas.append({i for i in m if i < n})

    dono: list[int | None] = [None] * n
    ok = 0
    for idx in sorted(range(len(achados)), key=lambda k: -len(marcadas[k])):
        for i in sorted(marcadas[idx]):
            if dono[i] is None and not citada_ok[i]:
                dono[i] = idx
            elif citada_ok[i]:
                ok += 1

    trechos: list[Trecho] = []
    atual: list[int] | None = None          # [fonte, primeira palavra, última palavra]
    for i in range(n):
        if dono[i] is None:
            continue
        if atual and atual[0] == dono[i] and i - atual[2] - 1 <= LACUNA:
            atual[2] = i
        else:
            if atual:
                trechos.append(Trecho(ini[atual[1]], fim[atual[2]], atual[0], atual[2] - atual[1] + 1, atual[1], atual[2]))
            atual = [dono[i], i, i]
    if atual:
        trechos.append(Trecho(ini[atual[1]], fim[atual[2]], atual[0], atual[2] - atual[1] + 1, atual[1], atual[2]))
    trechos = [t for t in trechos if t.palavras >= min(TAM_FONTE, 6)]
    for a in achados:
        a.palavras = 0
    for t in trechos:
        achados[t.fonte].palavras += t.palavras
    for a in achados:
        a.pct = 100.0 * a.palavras / n if n else 0.0

    # o mesmo trecho, visto do lado da fonte: onde ele está no trabalho encontrado
    for idx, a in enumerate(achados):
        if not a.palavras or not a.texto_fonte:
            continue
        _, nf, ini_f, fim_f = palavras_posicionadas(a.texto_fonte)
        mapa_f = mapa_shingles(nf, TAM_FONTE)
        meus = {sh for sh, ps in mapa(TAM_FONTE).items()
                if any(all(dono[p + k] == idx for k in range(TAM_FONTE) if p + k < n) for p in ps)}
        palavras_f = sorted({q + k for sh in meus if sh in mapa_f for q in mapa_f[sh]
                             for k in range(TAM_FONTE) if q + k < len(nf)})
        corridas: list[list[int]] = []
        for w in palavras_f:
            if corridas and w - corridas[-1][1] - 1 <= LACUNA:
                corridas[-1][1] = w
            else:
                corridas.append([w, w])
        a.marcas_fonte = [(ini_f[x], fim_f[y]) for x, y in corridas]
        for t in trechos:
            if t.fonte != idx:
                continue
            for p in range(t.palavra_ini, t.palavra_fim - TAM_FONTE + 2):
                achou = mapa_f.get(" ".join(norm[p:p + TAM_FONTE]))
                if achou:
                    t.fonte_ini = ini_f[achou[0]]
                    t.fonte_fim = next((e for b, e in a.marcas_fonte if b <= t.fonte_ini <= e), t.fonte_ini)
                    break
    return trechos, n, sum(t.palavras for t in trechos), ok


def procurar_na_internet(texto: str, ao_progredir: Progresso | None = None) -> ResultadoBusca:
    """Procura frases do texto e o assunto dele na internet. Lança ErroRede se nada pôde ser consultado."""
    avisar = ao_progredir or (lambda f, m: None)
    frases = escolher_frases(texto, 5, 9)
    chaves = palavras_chave(texto, 6)
    achados: dict[str, Achado] = {}
    total = len(frases) * 2 + 1
    feitas = sucessos = falhas = 0
    limite = erro_chave = False

    def tentar(func, arg):
        nonlocal sucessos, falhas, limite, erro_chave
        try:
            r = func(arg)
            sucessos += 1
            return r
        except ErroRede as e:
            falhas += 1
            if e.codigo == "limite":
                limite = True
            elif e.codigo == "chave":
                erro_chave = True
            return None

    for i, frase in enumerate(frases, 1):
        if limite:
            break
        avisar(0.7 * feitas / total, f"Procurando trechos do seu texto ({i} de {len(frases)})...")
        for o in (None if erro_chave else tentar(_openalex, f'"{frase}"')) or []:
            achados.setdefault(o["id"], _novo(o)).frases.append(frase)
        feitas += 1
        time.sleep(PAUSA)
        if limite:
            break
        for w in tentar(_wikipedia, frase) or []:
            titulo = w.get("title", "")
            chave = f"wiki:{w.get('pageid', titulo)}"
            a = achados.setdefault(chave, Achado(titulo, "Wikipédia", "", "Página da Wikipédia",
                                                 URL_PAGINA_WIKIPEDIA + urllib.parse.quote(titulo.replace(" ", "_")),
                                                 "Wikipédia", chave_fonte=titulo))
            a.frases.append(frase)
        feitas += 1
        time.sleep(PAUSA)

    if not limite and not erro_chave and chaves:
        avisar(0.7 * feitas / total, "Procurando trabalhos sobre o mesmo assunto...")
        res = tentar(_openalex, " ".join(chaves))
        if res == [] and len(chaves) > 3:
            res = tentar(_openalex, " ".join(chaves[:3]))
        for o in res or []:
            achados.setdefault(o["id"], _novo(o))

    if sucessos == 0:
        raise ErroRede("chave" if erro_chave else "limite" if limite else "rede")

    meus = set(mapa_shingles(tokenizar(texto)[1], 4))
    for a in achados.values():
        sh = list(mapa_shingles(tokenizar(a.resumo)[1], 4)) if a.resumo else []
        if sh:
            a.cobertura = sum(1 for x in sh if x in meus) / len(sh)
        if len(a.frases) >= 2 or a.cobertura >= 0.5:
            a.nivel = "alto"
        elif len(a.frases) == 1 or a.cobertura >= 0.2:
            a.nivel = "medio"
    ordem = {"alto": 0, "medio": 1, "tema": 2}
    lista = sorted(achados.values(), key=lambda a: (ordem[a.nivel], -len(a.frases), -a.cobertura))

    # baixa o texto das fontes suspeitas para comparar de verdade e marcar o que foi copiado
    suspeitas = [a for a in lista if a.nivel != "tema"][:MAX_FONTES]
    parcial = False
    for k, a in enumerate(suspeitas, 1):
        avisar(0.7 + 0.3 * (k - 1) / max(1, len(suspeitas)), f"Lendo a fonte {k} de {len(suspeitas)} para marcar os trechos copiados...")
        try:
            if a.fonte == "Wikipédia":
                a.texto_fonte, a.origem_texto = _wikipedia_texto(a.chave_fonte)[:600_000], "completo"
            elif a.pdf_url:
                a.texto_fonte, a.origem_texto = ler_pdf_bytes(baixar_bytes(a.pdf_url))[:600_000], "completo"
        except Exception:  # noqa: BLE001  (fonte indisponível: usa o resumo e os trechos achados)
            a.texto_fonte = ""
        if not a.texto_fonte.strip():
            a.texto_fonte, a.origem_texto = a.resumo, "resumo"
            parcial = True
    trechos, n_corpo, plagiadas, citadas_ok = _marcar_plagio(texto, lista)
    for a in lista:
        if a.palavras and a.pct >= 8:
            a.nivel = "alto"
        elif a.palavras and a.nivel == "tema":
            a.nivel = "medio"
        elif not a.palavras and a.nivel != "tema":
            a.nivel = "tema"      # coincidência só em citação correta (entre aspas, com fonte): não é cópia
    pct = 100.0 * plagiadas / n_corpo if n_corpo else 0.0
    return ResultadoBusca(lista, limite, falhas, sucessos, frases, trechos, pct, plagiadas, n_corpo, citadas_ok, parcial,
                          erro_chave)


# ---------------------------------------------------------------------------
# Conferir se as referências citadas existem na internet
# ---------------------------------------------------------------------------
@dataclass
class Existencia:
    situacao: str          # "encontrada", "nao_encontrada", "sem_titulo", "nao_verificada"
    titulo: str = ""
    link: str = ""


def _palavras_titulo(t: str) -> set[str]:
    return {n for n in (normalizar_token(p) for p in t.split()) if len(n) >= 3 and n not in STOP}


def verificar_existencia(titulos: list[str | None], ao_progredir: Progresso | None = None) -> list[Existencia]:
    avisar = ao_progredir or (lambda f, m: None)
    saida: list[Existencia] = []
    parar = False
    for i, titulo in enumerate(titulos):
        if not titulo or len(_palavras_titulo(titulo)) < 2:
            saida.append(Existencia("sem_titulo"))
            continue
        if parar:
            saida.append(Existencia("nao_verificada"))
            continue
        avisar(i / max(1, len(titulos)), f"Conferindo as referências na internet ({i + 1} de {len(titulos)})...")
        try:
            candidatos = _openalex(titulo)
        except ErroRede:
            parar = True
            saida.append(Existencia("nao_verificada"))
            continue
        alvo = _palavras_titulo(titulo)
        melhor, melhor_sim = None, 0.0
        for c in candidatos:
            sim = len(alvo & _palavras_titulo(c.get("display_name") or "")) / len(alvo)
            if sim > melhor_sim:
                melhor, melhor_sim = c, sim
        if melhor is not None and melhor_sim >= 0.75:
            saida.append(Existencia("encontrada", melhor.get("display_name") or "", _link(melhor)))
        else:
            saida.append(Existencia("nao_encontrada"))
        time.sleep(PAUSA)
    return saida
