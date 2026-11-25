"""Junta tudo: uma verificação completa do trabalho (busca na internet + referências)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .busca import Existencia, ResultadoBusca, procurar_na_internet, verificar_existencia
from .rede import ErroRede, tem_internet
from .referencias import AnaliseReferencias, analisar_referencias

MIN_PALAVRAS = 40
MAX_REFERENCIAS_ONLINE = 20

NOTA_LIMITES = ("A busca cobre artigos, teses, dissertações e preprints do catálogo aberto OpenAlex e a Wikipédia. "
                "Trabalhos que estão só em outros sites, em bases fechadas ou em repositórios que o catálogo não "
                "indexa não aparecem. Por isso \"nada igual\" não garante originalidade. Este programa aponta "
                "semelhanças e não substitui a avaliação de uma pessoa.")

MOTIVOS = {
    "offline": "Sem conexão com a internet: a busca por trabalhos parecidos não foi feita. Conecte-se e verifique de novo.",
    "limite": ("Os serviços de busca atingiram o limite de consultas por hoje. Tente de novo mais tarde ou aumente o "
               "limite colocando uma chave gratuita do OpenAlex em Configurações."),
    "chave": "O OpenAlex não aceitou a chave informada. Confira a chave em Configurações.",
    "rede": "Não foi possível acessar os serviços de busca. Confira a conexão com a internet e tente de novo.",
}


@dataclass
class Verificacao:
    nome: str
    texto: str
    online: bool
    busca: ResultadoBusca | None
    motivo: str | None                      # None, "offline", "limite" ou "rede"
    referencias: AnaliseReferencias
    existencia: list[Existencia] | None


def verificar(texto: str, nome: str, ao_progredir: Callable[[float, str], None] | None = None,
              conferir_referencias: bool = True) -> Verificacao:
    avisar = ao_progredir or (lambda f, m: None)
    avisar(0.02, "Conferindo a conexão com a internet...")
    online = tem_internet()
    avisar(0.05, "Analisando as referências do trabalho...")
    ref = analisar_referencias(texto)

    busca = existencia = None
    motivo = None
    if not online:
        motivo = "offline"
    else:
        try:
            busca = procurar_na_internet(texto, lambda f, m: avisar(0.1 + 0.6 * f, m))
            if busca.limite:
                motivo = "limite"
            elif busca.erro_chave:
                motivo = "chave"
        except ErroRede as e:
            motivo = e.codigo if e.codigo in ("limite", "rede", "chave") else "rede"
        if motivo is None and ref.entradas and conferir_referencias:
            titulos = [e.titulo for e in ref.entradas[:MAX_REFERENCIAS_ONLINE]]
            existencia = verificar_existencia(titulos, lambda f, m: avisar(0.7 + 0.28 * f, m))
            existencia += [Existencia("nao_verificada")] * (len(ref.entradas) - len(existencia))
    avisar(1.0, "Verificação concluída.")
    return Verificacao(nome, texto, online, busca, motivo, ref, existencia)


def pct_br(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def veredito_plagio(v: Verificacao) -> tuple[str, str, str]:
    """Devolve (estado, título, explicação). Estados: alto, medio, baixo, incompleto, nao_feito."""
    if v.busca is None:
        return "nao_feito", "Busca na internet não realizada", MOTIVOS.get(v.motivo or "rede", MOTIVOS["rede"])
    b = v.busca
    if b.palavras_plagiadas > 0:
        minimo = "pelo menos " if (b.parcial or v.motivo) else ""
        expl = "Os trechos copiados estão marcados no seu texto, com a fonte de cada um (aba Plágio)."
        if b.parcial:
            expl += " A porcentagem é o mínimo comprovado: algumas fontes só puderam ser comparadas pelo resumo."
        if b.palavras_citadas_ok:
            expl += (f" Outras {b.palavras_citadas_ok} palavras coincidem, mas estão entre aspas com a fonte indicada, "
                     "então não contam como plágio.")
        if v.motivo:
            expl += " Atenção: a busca ficou incompleta. " + MOTIVOS[v.motivo]
        if b.plagio_pct >= 10:
            return "alto", f"Encontramos plágio: {minimo}{pct_br(b.plagio_pct)}% do trabalho vem de outras fontes.", expl
        return "medio", f"Encontramos trechos copiados: {minimo}{pct_br(b.plagio_pct)}% do trabalho.", expl
    if v.motivo:
        return "incompleto", "Não achamos trabalho igual, mas a busca não terminou por completo.", MOTIVOS[v.motivo]
    return "baixo", "Não encontramos plágio no seu trabalho.", \
        "Nenhum trecho do texto apareceu em outros trabalhos das fontes consultadas."


def dados_grafico(v: Verificacao) -> dict:
    """O gráfico mostra: se há plágio, quanto do trabalho foi copiado; se não há, quanto do trabalho tem
    citações sem referência na lista (ou citações diretas sem fonte)."""
    estado = veredito_plagio(v)[0]
    if estado in ("alto", "medio") and v.busca:
        b = v.busca
        return {"tipo": "plagio", "pct": b.plagio_pct, "cor": "#C6432E",
                "titulo": "Quanto do trabalho foi copiado",
                "a": f"{b.palavras_plagiadas} palavras copiadas de outras fontes",
                "b": f"{b.palavras_corpo - b.palavras_plagiadas} palavras de texto próprio",
                "nota": "Mínimo comprovado." if (b.parcial or v.motivo) else ""}
    r = v.referencias
    total = max(r.palavras_corpo, 1)
    nota = ("Plágio não verificado: sem internet." if v.motivo == "offline"
            else "Plágio não verificado: a busca não pôde ser feita." if v.busca is None
            else "Plágio não verificado: a busca ficou incompleta." if estado == "incompleto"
            else "Nenhum plágio encontrado.")
    if r.referencias_sem_citacao:
        nota += f" Além disso, {len(r.referencias_sem_citacao)} referência(s) da lista nunca são citadas no texto."
    return {"tipo": "referencias", "pct": r.pct_sem_referencia, "cor": "#E0813F",
            "titulo": "Quanto do trabalho tem citação sem referência",
            "a": f"{r.palavras_sem_referencia} palavras em trechos com citação sem referência na lista",
            "b": f"{max(total - r.palavras_sem_referencia, 0)} palavras sem esse problema", "nota": nota}


VEREDITO_REFERENCIAS = {
    "adequado": "Referências adequadas",
    "parcial": "Referências parcialmente adequadas",
    "inadequado": "Referências inadequadas",
}
