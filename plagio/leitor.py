"""Leitura de arquivos de texto: TXT, DOCX, ODT, RTF e PDF."""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


class ErroLeitura(Exception):
    """Mensagem pensada para ser mostrada ao usuário."""


FORMATOS = (".txt", ".docx", ".odt", ".rtf", ".pdf")


def ler_arquivo(caminho: str | Path) -> str:
    p = Path(caminho)
    if not p.exists():
        raise ErroLeitura(f"Arquivo não encontrado: {p.name}")
    ext = p.suffix.lower()
    try:
        if ext == ".txt":
            return _quebras(_ler_txt(p))
        if ext == ".docx":
            return _quebras(_ler_docx(p))
        if ext == ".odt":
            return _quebras(_ler_odt(p))
        if ext == ".rtf":
            return _quebras(_ler_rtf(p))
        if ext == ".pdf":
            return _quebras(_ler_pdf(p))
    except ErroLeitura:
        raise
    except (zipfile.BadZipFile, ET.ParseError, OSError, ValueError) as e:
        raise ErroLeitura(f"Não foi possível abrir {p.name}: o arquivo parece estar corrompido ({e}).") from e
    if ext == ".doc":
        raise ErroLeitura("O formato .doc antigo não é aceito. Abra no Word e salve como .docx.")
    raise ErroLeitura(f'Formato "{ext or "?"}" não aceito. Use PDF, DOCX, TXT, RTF ou ODT.')


def _quebras(t: str) -> str:
    return t.replace("\r\n", "\n").replace("\r", "\n")


def _ler_txt(p: Path) -> str:
    dados = p.read_bytes()
    for cod in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return dados.decode(cod)
        except UnicodeDecodeError:
            continue
    raise ErroLeitura("Não foi possível decodificar o texto do arquivo.")


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _ler_docx(p: Path) -> str:
    with zipfile.ZipFile(p) as z:
        if "word/document.xml" not in z.namelist():
            raise ErroLeitura("Arquivo DOCX inválido.")
        raiz = ET.fromstring(z.read("word/document.xml"))
    paragrafos = []
    for par in raiz.iter(_W + "p"):
        partes = []
        for no in par.iter():
            if no.tag == _W + "t" and no.text:
                partes.append(no.text)
            elif no.tag == _W + "tab":
                partes.append("\t")
            elif no.tag == _W + "br":
                partes.append("\n")
        paragrafos.append("".join(partes))
    return "\n".join(paragrafos)


def _ler_odt(p: Path) -> str:
    with zipfile.ZipFile(p) as z:
        if "content.xml" not in z.namelist():
            raise ErroLeitura("Arquivo ODT inválido.")
        raiz = ET.fromstring(z.read("content.xml"))
    ns = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
    return "\n".join("".join(no.itertext()) for no in raiz.iter() if no.tag in (ns + "p", ns + "h"))


def _ler_rtf(p: Path) -> str:
    bruto = p.read_bytes().decode("cp1252", errors="replace")
    ignorar = ("fonttbl", "colortbl", "stylesheet", "info", "pict", "object", "generator")
    saida, i = [], 0
    while i < len(bruto):
        if bruto[i] == "{" and bruto[i + 1:i + 2] == "\\" and any(bruto.startswith("\\" + n, i + 1) for n in ignorar):
            prof, k = 1, i + 1
            while k < len(bruto) and prof:
                prof += (bruto[k] == "{") - (bruto[k] == "}")
                k += 1
            i = k
            continue
        saida.append(bruto[i])
        i += 1
    t = "".join(saida)

    def hexa(m):
        return bytes([int(m.group(1), 16)]).decode("cp1252", errors="replace")

    t = re.sub(r"\\par[d]?\b ?", "\n", t)
    t = re.sub(r"\\tab\b ?", "\t", t)
    t = re.sub(r"\\'([0-9a-fA-F]{2})", hexa, t)
    t = re.sub(r"\\u(-?\d+)\??", lambda m: chr(int(m.group(1)) % 65536), t)
    t = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", t)
    t = re.sub(r"[{}]", "", t).replace("\r", "")
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if not t:
        raise ErroLeitura("Não foi possível extrair texto deste RTF.")
    return t


def _ler_pdf(p: Path) -> str:
    return ler_pdf_bytes(p.read_bytes())


def ler_pdf_bytes(dados: bytes, max_paginas: int = 400) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ErroLeitura("Para ler PDF é preciso instalar o componente pypdf.\n"
                          "No terminal: pip install pypdf") from e
    import io
    leitor = PdfReader(io.BytesIO(dados))
    if leitor.is_encrypted:
        try:
            leitor.decrypt("")
        except Exception as e:  # noqa: BLE001
            raise ErroLeitura("Este PDF é protegido por senha.") from e
    texto = "\n".join((pg.extract_text() or "") for pg in list(leitor.pages)[:max_paginas])
    if not texto.strip():
        raise ErroLeitura("Este PDF não tem texto selecionável (talvez seja escaneado). "
                          "Tente um PDF gerado direto do editor de texto.")
    return texto
