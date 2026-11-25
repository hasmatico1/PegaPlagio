"""Relatório em texto simples, para salvar em arquivo."""
from __future__ import annotations

from datetime import datetime

from .comparacao import ResultadoLocal
from .verificacao import NOTA_LIMITES, VEREDITO_REFERENCIAS, Verificacao, dados_grafico, pct_br, veredito_plagio

ROTULO_NIVEL = {"alto": "muito parecido", "medio": "parecido", "tema": "mesmo assunto"}
ROTULO_STATUS = {"ok": "[ok]      ", "atencao": "[atenção] ", "problema": "[problema]"}
SITUACAO = {"encontrada": "encontrada na internet", "nao_encontrada": "não encontrada no catálogo",
            "sem_titulo": "título não identificado", "nao_verificada": "não verificada"}


def montar(v: Verificacao, locais: list[ResultadoLocal] | None = None) -> str:
    L: list[str] = []
    L += ["PEGA PLÁGIO - RELATÓRIO DE VERIFICAÇÃO", "=" * 60,
          f"Data: {datetime.now():%d/%m/%Y %H:%M}", f"Arquivo: {v.nome}",
          f"Palavras: {len(v.texto.split())}", ""]

    estado, titulo, resumo = veredito_plagio(v)
    L += ["1. PLÁGIO (BUSCA NA INTERNET)", "-" * 60, titulo, resumo, ""]
    if v.busca and v.busca.trechos:
        L += [f"Porcentagem do trabalho copiada: {pct_br(v.busca.plagio_pct)}% "
              f"({v.busca.palavras_plagiadas} de {v.busca.palavras_corpo} palavras)", "",
              "TRECHOS COPIADOS E DE ONDE VÊM"]
        for k, t in enumerate(v.busca.trechos, 1):
            a = v.busca.achados[t.fonte]
            trecho = " ".join(v.texto[t.ini:t.fim].split())
            L += [f"  {k}. \"{trecho[:140]}{'...' if len(trecho) > 140 else ''}\"",
                  f"     origem: {a.titulo} ({a.fonte}) {a.link}"]
            if t.fonte_ini >= 0:
                igual = " ".join(a.texto_fonte[t.fonte_ini:t.fonte_fim].split())
                L.append(f"     no trabalho encontrado: \"{igual[:140]}{'...' if len(igual) > 140 else ''}\"")
        L.append("")
    g = dados_grafico(v)
    L += [f"GRÁFICO: {g['titulo']}: {pct_br(g['pct'])}%", f"   {g['a']}", f"   {g['b']}", f"   {g['nota']}".rstrip(), ""]
    if v.busca:
        for i, a in enumerate([a for a in v.busca.achados if a.nivel != "tema"], 1):
            L += [f"{i}. {a.titulo}", f"   {a.tipo} | {a.ano or 's/d'} | {a.autores} | fonte: {a.fonte}",
                  f"   Link: {a.link}", f"   Grau: {ROTULO_NIVEL[a.nivel]}"
                  + (f" ({pct_br(a.pct)}% do trabalho vem daqui)" if a.palavras else "")]
            L += [f'   Trecho encontrado: "{f}"' for f in a.frases]
            if a.cobertura >= 0.2:
                L.append(f"   {round(a.cobertura * 100)}% do resumo desse trabalho aparece no texto enviado")
            L.append("")
        temas = [a for a in v.busca.achados if a.nivel == "tema"]
        if temas:
            L.append("Mesmo assunto, sem trechos iguais:")
            L += [f"   - {a.titulo} ({a.ano or 's/d'}) {a.link}" for a in temas[:4]] + [""]
    L += [NOTA_LIMITES, ""]

    r = v.referencias
    L += ["2. REFERÊNCIAS", "-" * 60, VEREDITO_REFERENCIAS[r.veredito].upper(), ""]
    L += [f"{ROTULO_STATUS[i.status]} {i.texto}" for i in r.itens]
    if r.citadas_sem_referencia:
        L += ["", "Citadas no texto, mas ausentes da lista:"] + [f"   - {c}" for c in r.citadas_sem_referencia]
    if r.referencias_sem_citacao:
        L += ["", "Na lista, mas não citadas no texto:"] + [f"   - {e.texto[:100]}" for e in r.referencias_sem_citacao]
    if r.aspas_sem_fonte:
        L += ["", "Citações diretas sem fonte:"] + [f'   - "{t}"' for t in r.aspas_sem_fonte]
    if r.entradas:
        L += ["", "Conferência de cada referência:"]
        for i, e in enumerate(r.entradas):
            L.append(f"   {i + 1}. {e.texto[:110]}")
            for p in e.problemas:
                L.append(f"        - {p}")
            if v.existencia and i < len(v.existencia):
                ex = v.existencia[i]
                L.append(f"        - internet: {SITUACAO[ex.situacao]}" + (f" ({ex.link})" if ex.link else ""))
    L.append("")

    if locais:
        L += ["3. COMPARAÇÃO COM ARQUIVOS FORNECIDOS", "-" * 60]
        for x in locais:
            L += [f"{x.nome}: {x.cobertura:.1f}% do texto aparece nele (risco {x.risco})"]
            L += [f'   - "{t}"' for t in x.trechos]
        L.append("")
    return "\n".join(L)
