"""Servidor de mentira que imita OpenAlex, Wikipédia e um PDF de repositório, para testar sem internet."""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

WIKI = ("A fotossíntese é o processo biológico pelo qual plantas, algas e algumas bactérias convertem energia luminosa "
        "em energia química armazenada em moléculas de glicose. Esse processo ocorre principalmente nos cloroplastos, "
        "organelas que contêm clorofila, o pigmento responsável pela cor verde das folhas. Durante a fase clara, a luz "
        "solar é absorvida e a água é decomposta, liberando oxigênio para a atmosfera.")
DISS = ("O ensino de ciências nas escolas públicas brasileiras enfrenta dificuldades históricas relacionadas à formação "
        "de professores, à falta de laboratórios equipados e ao excesso de conteúdos conceituais desvinculados do "
        "cotidiano dos estudantes. Pesquisas recentes indicam que metodologias ativas, como a aprendizagem baseada em "
        "projetos, aumentam significativamente o interesse e o desempenho dos alunos. Contudo, a implementação dessas "
        "metodologias exige tempo de planejamento coletivo, apoio da gestão escolar e políticas públicas consistentes "
        "de valorização docente.")
RESUMO = DISS.split(". ")[0] + "."
RESUMO_RUIM = "Estudo sobre redes neurais."


def limpar(x):
    return re.sub(r"[^\w\s]", "", x.lower())


def fazer_pdf(texto):
    palavras, linhas, atual = texto.split(), [], ""
    for p in palavras:
        if len(atual) + len(p) > 85:
            linhas.append(atual); atual = ""
        atual += (" " if atual else "") + p
    linhas.append(atual)
    esc = lambda l: l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    fluxo = "BT /F1 11 Tf 72 740 Td 14 TL\n" + "\n".join(f"({esc(l)}) '" for l in linhas) + "\nET"
    corpo = fluxo.encode("cp1252")
    objs = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
            b"<</Length %d>>\nstream\n" % len(corpo) + corpo + b"\nendstream",
            b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica/Encoding/WinAnsiEncoding>>"]
    pdf, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(pdf)); pdf += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    return pdf + b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, x)


def obra(i, titulo, resumo=None, pdf_url=None):
    idx = {}
    for p, w in enumerate((resumo or "").split()):
        idx.setdefault(w, []).append(p)
    return {"id": f"https://openalex.org/W{i}", "display_name": titulo, "publication_year": 2021, "doi": None,
            "type": "dissertation", "authorships": [{"author": {"display_name": "Maria Silva"}}],
            "abstract_inverted_index": idx or None,
            "primary_location": {"landing_page_url": f"https://repositorio.exemplo.br/{i}", "pdf_url": pdf_url},
            "best_oa_location": {"pdf_url": pdf_url} if pdf_url else None}


class H(BaseHTTPRequestHandler):
    modo = "copia"          # "copia" | "limite"
    porta = 0
    consultas: list = []

    def log_message(self, *a):
        pass

    def _enviar(self, status, tipo, dados):
        self.send_response(status); self.send_header("Content-Type", tipo); self.end_headers(); self.wfile.write(dados)

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        H.consultas.append(self.path)
        if H.modo == "limite":
            return self._enviar(429, "text/plain", b"")
        if H.modo == "limite409":
            return self._enviar(409, "text/plain", b"")
        if H.modo == "exigir_chave" and u.path == "/openalex" and q.get("api_key", [""])[0] != "BOA":
            return self._enviar(401, "text/plain", b"")
        if u.path == "/pdf/1":
            return self._enviar(200, "application/pdf", fazer_pdf(DISS))
        if u.path == "/openalex":
            busca = q["search"][0]
            if busca.startswith('"'):
                achou = limpar(busca.strip('"')) in limpar(DISS)
                res = [obra(1, "Ensino de ciências nas escolas públicas: uma dissertação", RESUMO,
                            f"http://127.0.0.1:{H.porta}/pdf/1")] if achou else []
            elif "Mediação" in busca:
                res = [obra(7, "Mediação pedagógica hoje")]
            else:
                res = [obra(2, "Redes neurais e ensino", RESUMO_RUIM)]
            return self._enviar(200, "application/json", json.dumps({"results": res}).encode())
        # Wikipédia
        if "prop" in q:
            corpo = {"query": {"pages": {"5": {"title": "Fotossíntese", "extract": WIKI}}}}
        else:
            achou = limpar(q["srsearch"][0].strip('"')) in limpar(WIKI)
            corpo = {"query": {"search": [{"title": "Fotossíntese", "pageid": 5, "snippet": "..."}] if achou else []}}
        self._enviar(200, "application/json", json.dumps(corpo).encode())


def iniciar():
    srv = HTTPServer(("127.0.0.1", 0), H)
    H.porta = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, H.porta


def apontar_para(porta):
    from plagio import busca, rede
    busca.URL_OPENALEX = f"http://127.0.0.1:{porta}/openalex"
    busca.URL_WIKIPEDIA = f"http://127.0.0.1:{porta}/wiki"
    busca.PAUSA = 0
    rede.HOSTS_TESTE = [("127.0.0.1", porta)]


ORIGINAL1 = ("Este trabalho investiga como estudantes do ensino médio compreendem fenômenos naturais presentes na rotina "
             "de suas famílias. A pesquisa foi realizada em duas escolas da região metropolitana durante o segundo "
             "semestre, com observações em sala de aula e entrevistas semiestruturadas. Os resultados preliminares "
             "apontam grande curiosidade, mas pouca familiaridade com termos científicos básicos.")
ORIGINAL2 = ("Na segunda etapa, os participantes registraram em cadernos de campo situações do cotidiano que consideravam "
             "científicas, como o cozimento de alimentos, a secagem de roupas ao sol e o funcionamento de aparelhos "
             "elétricos domésticos, e depois discutiram essas anotações em pequenos grupos mediados pela pesquisadora.")


def trabalho_exemplo():
    wiki = " ".join(WIKI.split(". ")[:2]) + "."
    wiki = wiki.replace("principalmente", "sobretudo")      # pequena troca para testar a tolerância
    diss = ". ".join(DISS.split(". ")[:2]) + "."
    citada = ('Para Santos (2020), "Contudo, a implementação dessas metodologias exige tempo de planejamento coletivo, '
              'apoio da gestão escolar e políticas públicas consistentes de valorização docente".')
    refs = ("REFERÊNCIAS\n\nSANTOS, Paulo. Metodologias ativas no ensino. São Paulo: Atlas, 2020.\n\n"
            "SILVA, Maria. Ensino de ciências nas escolas públicas. Dissertação (Mestrado). USP, 2021.\n")
    return "\n\n".join([ORIGINAL1, wiki, ORIGINAL2, diss, citada]) + "\n\n" + refs
