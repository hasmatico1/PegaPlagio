"""Janela do programa (tkinter, já vem com o Python)."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from . import busca, comparacao, config, leitor, rede
from .relatorio import montar
from .texto import contar_palavras
from .verificacao import (MIN_PALAVRAS, MOTIVOS, NOTA_LIMITES, VEREDITO_REFERENCIAS, Verificacao, dados_grafico,
                          pct_br, verificar, veredito_plagio)

PAPEL, CARTAO, TINTA, SUAVE, VERDE, VERDE_ESC = "#ECEEE4", "#F6F7F1", "#1C2624", "#4F5D59", "#1F5C4F", "#123B32"
CORES = {"ok": ("#DCE7E1", "#14422F"), "aviso": ("#F7E8C4", "#6B4A00"),
         "ruim": ("#F3D9D3", "#7A2416"), "neutro": ("#E1E4D6", "#333B38")}
PALETA = ["#F6DC9B", "#BFE0F0", "#D9C6EC", "#C6E8C5", "#F5C2C2", "#F8D6A8"]   # uma cor por fonte
MARCA = {"baixo": "#D5E8C5", "medio": "#F6DC9B", "alto": "#F2B98E", "critico": "#EE9C8E"}
COR_PLAGIO = {"alto": "ruim", "medio": "aviso", "baixo": "ok", "incompleto": "aviso", "nao_feito": "neutro"}
COR_REFS = {"adequado": "ok", "parcial": "aviso", "inadequado": "ruim"}
ROTULO_NIVEL = {"alto": "Muito parecido", "medio": "Parecido", "tema": "Mesmo assunto"}
ROTULO_RISCO = {"baixo": "Baixo", "medio": "Médio", "alto": "Alto", "critico": "Crítico"}
SITUACAO = {"encontrada": "Encontrada", "nao_encontrada": "Não encontrada", "sem_titulo": "Sem título",
            "nao_verificada": "Não verificada"}
ICONE = {"ok": "✔", "atencao": "!", "problema": "✖"}

BANNER_ON = "●  Conectado à internet. A busca por trabalhos parecidos está disponível."
BANNER_OFF = ("●  Sem internet. A busca por trabalhos parecidos está desativada. "
              "As referências e a comparação com seus arquivos continuam funcionando.")
AVISO_OFFLINE = ("O computador está sem conexão com a internet.\n\n"
                 "A busca por trabalhos parecidos não pode ser feita agora. Conecte-se e verifique de novo.\n\n"
                 "Vou analisar apenas as referências do trabalho.")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Pega Plágio")
        self.geometry("1060x800")
        self.minsize(900, 640)
        self.configure(bg=PAPEL)
        fam = tkfont.nametofont("TkDefaultFont").actual("family")
        self.f = {"n": (fam, 10), "b": (fam, 10, "bold"), "g": (fam, 12, "bold"), "t": ("Georgia", 22),
                  "c": (fam, 14, "bold"), "m": ("Consolas", 10)}

        self.texto = ""
        self.nome = ""
        self.verif: Verificacao | None = None
        self.achados_na_tela: list = []
        self.trechos_sel: list = []
        self.nav_i = 0
        self.arquivos_locais: list[tuple[str, str]] = []
        self.locais: list[comparacao.ResultadoLocal] = []
        self.ocupado = False
        self.online: bool | None = None
        self._checando_rede = False
        self.fila: queue.Queue = queue.Queue()
        self.cfg = config.carregar()
        busca.definir_chave(self.cfg["openalex_chave"])
        self._depois: dict[str, str] = {}
        self._avisou_offline = False
        self.protocol("WM_DELETE_WINDOW", self._fechar)

        self._estilos()
        self._montar()
        self.after(100, self._ler_fila)
        self._checar_rede()

    def _fechar(self) -> None:
        for ident in self._depois.values():
            try:
                self.after_cancel(ident)
            except tk.TclError:
                pass
        self.destroy()

    # ------------------------------------------------------------------ montagem
    def _estilos(self) -> None:
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TNotebook", background=PAPEL, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(16, 8), font=self.f["n"], background="#DDE0D2", foreground=SUAVE)
        s.map("TNotebook.Tab", background=[("selected", CARTAO)], foreground=[("selected", TINTA)])
        s.configure("Treeview", rowheight=26, background=CARTAO, fieldbackground=CARTAO, foreground=TINTA,
                    font=self.f["n"], borderwidth=0)
        s.configure("Treeview.Heading", font=self.f["b"], background="#DDE0D2", foreground=TINTA)
        s.configure("TButton", font=self.f["n"], padding=(12, 6))
        s.configure("Primario.TButton", font=self.f["g"], foreground="white", background=VERDE, padding=(22, 11))
        s.map("Primario.TButton", background=[("active", VERDE_ESC), ("disabled", "#9CB3AB")],
              foreground=[("disabled", "#F0F4F2")])
        s.configure("TProgressbar", troughcolor="#DDE0D2", background=VERDE, borderwidth=0)

    def _rotulo(self, pai, texto, fonte, cor=TINTA, **kw) -> tk.Label:
        return tk.Label(pai, text=texto, font=fonte, fg=cor, bg=kw.pop("bg", PAPEL), **kw)

    def _montar(self) -> None:
        self.banner = tk.Label(self, text="Conferindo a conexão com a internet...", anchor="w", padx=18, pady=8,
                               font=self.f["b"], bg=CORES["neutro"][0], fg=CORES["neutro"][1])
        self.banner.pack(fill="x")

        corpo = tk.Frame(self, bg=PAPEL)
        corpo.pack(fill="both", expand=True, padx=22, pady=(14, 10))
        self._rotulo(corpo, "Pega Plágio", self.f["t"]).pack(anchor="w")
        self._rotulo(corpo, "Seu trabalho já existe por aí? Escolha o arquivo (PDF, Word, TXT, RTF ou ODT) e clique em verificar.",
                     self.f["n"], SUAVE).pack(anchor="w", pady=(2, 10))

        linha = tk.Frame(corpo, bg=PAPEL)
        linha.pack(fill="x")
        self.btn_escolher = ttk.Button(linha, text="Escolher arquivo...", command=self.escolher)
        self.btn_escolher.pack(side="left")
        self.btn_colar = ttk.Button(linha, text="Colar texto", command=self.colar)
        self.btn_colar.pack(side="left", padx=8)
        self.lbl_arquivo = self._rotulo(linha, "Nenhum arquivo escolhido.", self.f["n"], SUAVE)
        self.lbl_arquivo.pack(side="left", padx=10)
        ttk.Button(linha, text="Configurações...", command=self.abrir_config).pack(side="right")

        acao = tk.Frame(corpo, bg=PAPEL)
        acao.pack(fill="x", pady=12)
        self.btn_verificar = ttk.Button(acao, text="Verificar plágio e referências", style="Primario.TButton",
                                        command=self.verificar_clique, state="disabled")
        self.btn_verificar.pack(side="left")
        self.area_prog = tk.Frame(acao, bg=PAPEL)
        self.prog = ttk.Progressbar(self.area_prog, maximum=100, length=360)
        self.prog.pack(anchor="w")
        self.lbl_prog = self._rotulo(self.area_prog, "", self.f["n"], SUAVE)
        self.lbl_prog.pack(anchor="w")

        self.var_conferir = tk.BooleanVar(value=self.cfg["conferir_referencias"])
        self.var_conferir.trace_add("write", lambda *_: self._salvar_cfg(conferir_referencias=self.var_conferir.get()))
        tk.Checkbutton(corpo, text="Conferir na internet se as obras da lista de referências existem (gasta mais buscas)",
                       variable=self.var_conferir, font=self.f["n"], bg=PAPEL, fg=SUAVE, activebackground=PAPEL,
                       selectcolor=CARTAO, anchor="w").pack(anchor="w", pady=(0, 8))

        self.abas = ttk.Notebook(corpo)
        self.abas.pack(fill="both", expand=True)
        self._aba_resumo()
        self._aba_plagio()
        self._aba_iguais()
        self._aba_referencias()
        self._aba_arquivos()

        rodape = tk.Frame(corpo, bg=PAPEL)
        rodape.pack(fill="x", pady=(10, 0))
        self.btn_salvar = ttk.Button(rodape, text="Salvar relatório...", command=self.salvar, state="disabled")
        self.btn_salvar.pack(side="left")
        self._rotulo(rodape, "Este programa aponta semelhanças e não substitui a avaliação de uma pessoa.",
                     self.f["n"], SUAVE).pack(side="right")

    def _cartao(self, pai) -> tuple[tk.Frame, tk.Label, tk.Label]:
        quadro = tk.Frame(pai, bd=0)
        titulo = tk.Label(quadro, font=self.f["c"], anchor="w", justify="left", padx=16, pady=(12))
        titulo.pack(fill="x")
        texto = tk.Label(quadro, font=self.f["n"], anchor="w", justify="left", padx=16)
        texto.pack(fill="x", pady=(0, 12))
        quadro.bind("<Configure>", lambda e, a=titulo, b=texto: (a.config(wraplength=e.width - 40),
                                                                  b.config(wraplength=e.width - 40)))
        return quadro, titulo, texto

    def _pintar(self, cartao, cor: str) -> None:
        bg, fg = CORES[cor]
        quadro, titulo, texto = cartao
        for w in (quadro, titulo, texto):
            w.config(bg=bg)
        titulo.config(fg=fg)
        texto.config(fg=fg)

    def _texto_somente_leitura(self, pai, altura: int) -> tk.Text:
        t = tk.Text(pai, height=altura, wrap="word", font=self.f["n"], bg=CARTAO, fg=TINTA, relief="flat",
                    padx=12, pady=8, state="disabled", highlightthickness=1, highlightbackground="#D5D8CB")
        for nome, cor in (("ok", "#14422F"), ("atencao", "#8A5D06"), ("problema", "#A22E1B")):
            t.tag_configure(nome, foreground=cor, font=self.f["b"])
        t.tag_configure("negrito", font=self.f["b"])
        t.tag_configure("suave", foreground=SUAVE)
        for nome, cor in MARCA.items():
            t.tag_configure("marca_" + nome, background=cor)
        return t

    def _escrever(self, t: tk.Text, partes: list[tuple[str, str]]) -> None:
        t.config(state="normal")
        t.delete("1.0", "end")
        for texto, tag in partes:
            t.insert("end", texto, tag or ())
        t.config(state="disabled")

    # --- abas
    def _aba_resumo(self) -> None:
        aba = tk.Frame(self.abas, bg=CARTAO)
        self.abas.add(aba, text="Resumo")
        aba.columnconfigure(1, weight=1)
        # gráfico à esquerda
        graf = tk.Frame(aba, bg=CARTAO)
        graf.grid(row=0, column=0, sticky="n", padx=(16, 4), pady=14)
        self.canvas = tk.Canvas(graf, width=240, height=230, bg=CARTAO, highlightthickness=0)
        self.canvas.pack()
        self.lbl_g_titulo = tk.Label(graf, font=self.f["b"], bg=CARTAO, fg=TINTA, wraplength=240, justify="center")
        self.lbl_g_titulo.pack(pady=(2, 6))
        self.lbl_g_a = tk.Label(graf, font=self.f["n"], bg=CARTAO, fg=SUAVE, wraplength=240, justify="left", anchor="w")
        self.lbl_g_a.pack(fill="x")
        self.lbl_g_b = tk.Label(graf, font=self.f["n"], bg=CARTAO, fg=SUAVE, wraplength=240, justify="left", anchor="w")
        self.lbl_g_b.pack(fill="x")
        self.lbl_g_nota = tk.Label(graf, font=self.f["n"], bg=CARTAO, fg=SUAVE, wraplength=240, justify="left", anchor="w")
        self.lbl_g_nota.pack(fill="x", pady=(6, 0))
        self._desenhar_grafico(None)
        # cartões à direita
        dir_ = tk.Frame(aba, bg=CARTAO)
        dir_.grid(row=0, column=1, sticky="new", padx=(8, 14), pady=14)
        self.card_plagio = self._cartao(dir_)
        self.card_refs = self._cartao(dir_)
        self.card_plagio[0].pack(fill="x", pady=(0, 8))
        self.card_refs[0].pack(fill="x", pady=(0, 8))
        self._pintar(self.card_plagio, "neutro")
        self._pintar(self.card_refs, "neutro")
        self.card_plagio[1].config(text="Plágio")
        self.card_plagio[2].config(text="O resultado aparece aqui depois da verificação.")
        self.card_refs[1].config(text="Referências")
        self.card_refs[2].config(text="O resultado aparece aqui depois da verificação.")
        self.lbl_nota = tk.Label(dir_, text="", font=self.f["n"], fg=SUAVE, bg=CARTAO, justify="left", anchor="w")
        self.lbl_nota.pack(fill="x", pady=(4, 0))
        dir_.bind("<Configure>", lambda e: self.lbl_nota.config(wraplength=e.width - 10))

    def _desenhar_grafico(self, dados: dict | None) -> None:
        c = self.canvas
        c.delete("all")
        cx, cy, raio, esp = 120, 112, 86, 28
        caixa = (cx - raio, cy - raio, cx + raio, cy + raio)
        c.create_oval(*caixa, outline="#DDE0D2", width=esp)
        fam = self.f["n"][0]
        if dados is None:
            c.create_text(cx, cy, text="—", font=(fam, 26, "bold"), fill=SUAVE)
            self.lbl_g_titulo.config(text="O gráfico aparece depois da verificação.")
            for w in (self.lbl_g_a, self.lbl_g_b, self.lbl_g_nota):
                w.config(text="")
            return
        pct = max(0.0, min(100.0, dados["pct"]))
        if pct > 0:
            c.create_arc(*caixa, start=90, extent=-min(pct, 99.99) * 3.6, style="arc", outline=dados["cor"], width=esp)
        c.create_text(cx, cy - 8, text=pct_br(pct) + "%", font=(fam, 26, "bold"), fill=TINTA)
        c.create_text(cx, cy + 22, text="do trabalho", font=(fam, 10), fill=SUAVE)
        self.lbl_g_titulo.config(text=dados["titulo"])
        self.lbl_g_a.config(text="■  " + dados["a"], fg=dados["cor"])
        self.lbl_g_b.config(text="■  " + dados["b"], fg="#9AA39F")
        self.lbl_g_nota.config(text=dados["nota"], fg=SUAVE)

    def _aba_plagio(self) -> None:
        aba = tk.Frame(self.abas, bg=CARTAO)
        self.abas.add(aba, text="Plágio")
        self.tree_achados = ttk.Treeview(aba, columns=("n", "grau", "fonte", "titulo", "pct"), show="headings",
                                         height=5, selectmode="browse")
        for c, t, w in (("n", "Nº", 36), ("grau", "Grau", 130), ("fonte", "Fonte", 90), ("titulo", "Título", 420),
                        ("pct", "% do trabalho", 125)):
            self.tree_achados.heading(c, text=t)
            self.tree_achados.column(c, width=w, anchor="w", stretch=(c == "titulo"))
        self.tree_achados.pack(fill="x", padx=10, pady=(10, 4))
        self.tree_achados.bind("<<TreeviewSelect>>", self._selecionar_fonte)
        self.tree_achados.bind("<Double-1>", lambda e: self.abrir_achado())
        self.lbl_origem = tk.Label(aba, text="", font=self.f["b"], bg=CARTAO, fg=TINTA, justify="left", anchor="w")
        self.lbl_origem.pack(fill="x", padx=12, pady=(2, 4))
        aba.bind("<Configure>", lambda e: self.lbl_origem.config(wraplength=e.width - 30))
        quadro = tk.Frame(aba, bg=CARTAO)
        quadro.pack(fill="both", expand=True, padx=10)
        self.txt_trabalho = self._texto_somente_leitura(quadro, 10)
        rolagem = ttk.Scrollbar(quadro, command=self.txt_trabalho.yview)
        self.txt_trabalho.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.txt_trabalho.pack(side="left", fill="both", expand=True)
        for i, cor in enumerate(PALETA):
            self.tree_achados.tag_configure(f"c{i}", background=cor)
        self.btn_abrir = ttk.Button(aba, text="Abrir a fonte no navegador", command=self.abrir_achado, state="disabled")
        self.btn_abrir.pack(anchor="w", padx=10, pady=8)
        self.lbl_origem.config(text="O trabalho, com os trechos copiados marcados, aparece aqui depois da verificação.",
                               fg=SUAVE)

    def _aba_iguais(self) -> None:
        aba = tk.Frame(self.abas, bg=CARTAO)
        self.abas.add(aba, text="Trabalhos iguais")
        self.lbl_iguais = tk.Label(aba, text="Quando o programa achar trabalhos com trechos iguais ao seu, eles aparecem aqui, "
                                   "lado a lado com o seu, com o trecho copiado marcado nos dois.",
                                   font=self.f["n"], bg=CARTAO, fg=SUAVE, justify="left", anchor="w")
        self.lbl_iguais.pack(fill="x", padx=12, pady=(10, 4))
        aba.bind("<Configure>", lambda e: self.lbl_iguais.config(wraplength=e.width - 30))
        self.tree_iguais = ttk.Treeview(aba, columns=("n", "titulo", "fonte", "pct", "trechos"), show="headings",
                                        height=3, selectmode="browse")
        for c, t, w in (("n", "Nº", 36), ("titulo", "Trabalho encontrado", 420), ("fonte", "Fonte", 90),
                        ("pct", "% do seu trabalho", 150), ("trechos", "Trechos", 80)):
            self.tree_iguais.heading(c, text=t)
            self.tree_iguais.column(c, width=w, anchor="w", stretch=(c == "titulo"))
        self.tree_iguais.pack(fill="x", padx=10, pady=(0, 4))
        self.tree_iguais.bind("<<TreeviewSelect>>", self._selecionar_igual)
        for i, cor in enumerate(PALETA):
            self.tree_iguais.tag_configure(f"c{i}", background=cor)
        self.lbl_igual_info = tk.Label(aba, text="", font=self.f["b"], bg=CARTAO, fg=TINTA, justify="left", anchor="w")
        self.lbl_igual_info.pack(fill="x", padx=12)
        barra = tk.Frame(aba, bg=CARTAO)
        barra.pack(fill="x", padx=10, pady=6)
        self.btn_ant = ttk.Button(barra, text="◀ Trecho anterior", command=lambda: self._ir_trecho(self.nav_i - 1))
        self.btn_ant.pack(side="left")
        self.lbl_trecho = tk.Label(barra, text="", font=self.f["b"], bg=CARTAO, fg=TINTA, width=16)
        self.lbl_trecho.pack(side="left")
        self.btn_prox = ttk.Button(barra, text="Próximo trecho ▶", command=lambda: self._ir_trecho(self.nav_i + 1))
        self.btn_prox.pack(side="left")
        self.btn_abrir_igual = ttk.Button(barra, text="Abrir o trabalho encontrado no navegador",
                                          command=self._abrir_igual, state="disabled")
        self.btn_abrir_igual.pack(side="right")
        painel = ttk.PanedWindow(aba, orient="horizontal")
        painel.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.txt_igual_meu = self._lado(painel, "Seu trabalho")
        self.txt_igual_fonte = self._lado(painel, "Trabalho encontrado")

    def _lado(self, painel, titulo: str) -> tk.Text:
        quadro = tk.Frame(painel, bg=CARTAO)
        painel.add(quadro, weight=1)
        tk.Label(quadro, text=titulo, font=self.f["b"], bg=CARTAO, fg=SUAVE, anchor="w").pack(fill="x")
        corpo = tk.Frame(quadro, bg=CARTAO)
        corpo.pack(fill="both", expand=True)
        t = self._texto_somente_leitura(corpo, 8)
        rolagem = ttk.Scrollbar(corpo, command=t.yview)
        t.config(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        return t

    def _aba_referencias(self) -> None:
        aba = tk.Frame(self.abas, bg=CARTAO)
        self.abas.add(aba, text="Referências")
        self.txt_refs = self._texto_somente_leitura(aba, 7)
        self.txt_refs.pack(fill="x", padx=10, pady=(10, 6))
        cols = ("n", "ref", "formato", "internet")
        self.tree_refs = ttk.Treeview(aba, columns=cols, show="headings", height=6, selectmode="browse")
        for c, t, w in (("n", "Nº", 40), ("ref", "Referência", 560), ("formato", "Formato", 110),
                        ("internet", "Na internet", 120)):
            self.tree_refs.heading(c, text=t)
            self.tree_refs.column(c, width=w, anchor="w", stretch=(c == "ref"))
        self.tree_refs.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self.tree_refs.bind("<<TreeviewSelect>>", self._detalhe_ref)
        self.txt_ref_detalhe = self._texto_somente_leitura(aba, 4)
        self.txt_ref_detalhe.pack(fill="x", padx=10, pady=(0, 10))
        self._escrever(self.txt_refs, [("A conferência das referências aparece aqui depois da verificação.", "suave")])

    def _aba_arquivos(self) -> None:
        aba = tk.Frame(self.abas, bg=CARTAO)
        self.abas.add(aba, text="Comparar com meus arquivos")
        topo = tk.Frame(aba, bg=CARTAO)
        topo.pack(fill="x", padx=10, pady=10)
        ttk.Button(topo, text="Adicionar arquivos...", command=self.adicionar_locais).pack(side="left")
        ttk.Button(topo, text="Remover selecionado", command=self.remover_local).pack(side="left", padx=8)
        self.btn_comparar = ttk.Button(topo, text="Comparar", command=self.comparar_locais, state="disabled")
        self.btn_comparar.pack(side="left")
        self.lista_locais = tk.Listbox(aba, height=3, font=self.f["n"], bg=CARTAO, relief="flat",
                                       highlightthickness=1, highlightbackground="#D5D8CB", activestyle="none")
        self.lista_locais.pack(fill="x", padx=10)
        cols = ("nome", "pct", "risco")
        self.tree_locais = ttk.Treeview(aba, columns=cols, show="headings", height=4, selectmode="browse")
        for c, t, w in (("nome", "Arquivo", 520), ("pct", "% do seu texto que aparece nele", 220), ("risco", "Risco", 100)):
            self.tree_locais.heading(c, text=t)
            self.tree_locais.column(c, width=w, anchor="w", stretch=(c == "nome"))
        self.tree_locais.pack(fill="x", padx=10, pady=8)
        self.tree_locais.bind("<<TreeviewSelect>>", self._detalhe_local)
        self.txt_local = self._texto_somente_leitura(aba, 8)
        self.txt_local.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._escrever(self.txt_local, [("Útil para conferir o trabalho contra colegas ou fontes que você juntou. "
                                         "Os trechos iguais aparecem marcados no seu texto.", "suave")])

    # ------------------------------------------------------------------ internet
    def _checar_rede(self) -> None:
        if not self._checando_rede:
            self._checando_rede = True
            fila = self.fila
            threading.Thread(target=lambda: fila.put(("rede", rede.tem_internet())), daemon=True).start()
        self._depois["rede"] = self.after(6000, self._checar_rede)

    def _aplicar_rede(self, ok: bool) -> None:
        self._checando_rede = False
        self.online = ok
        bg, fg = CORES["ok" if ok else "ruim"]
        self.banner.config(text=BANNER_ON if ok else BANNER_OFF, bg=bg, fg=fg, wraplength=self.winfo_width() - 40)
        self.btn_verificar.config(text="Verificar plágio e referências" if ok
                                  else "Verificar só as referências (sem internet)")

    # ------------------------------------------------------------------ arquivo
    def escolher(self) -> None:
        caminho = filedialog.askopenfilename(
            title="Escolha o trabalho", filetypes=[("Documentos", "*.pdf *.docx *.txt *.rtf *.odt"), ("Todos", "*.*")])
        if caminho:
            self.carregar(caminho)

    def carregar(self, caminho: str) -> None:
        try:
            texto = leitor.ler_arquivo(caminho)
        except leitor.ErroLeitura as e:
            messagebox.showerror("Não foi possível ler o arquivo", str(e))
            return
        if not texto.strip():
            messagebox.showerror("Arquivo vazio", "O arquivo não tem texto.")
            return
        self.definir_texto(texto, Path(caminho).name)

    def definir_texto(self, texto: str, nome: str) -> None:
        texto = texto.replace("\r\n", "\n").replace("\r", "\n")
        self.texto, self.nome = texto, nome
        self.lbl_arquivo.config(text=f"{nome}  ({contar_palavras(texto):,} palavras)".replace(",", "."), fg=TINTA)
        self.btn_verificar.config(state="normal")
        self._atualizar_comparar()

    def colar(self) -> None:
        j = tk.Toplevel(self)
        j.title("Colar texto")
        j.geometry("640x420")
        j.configure(bg=PAPEL)
        caixa = tk.Text(j, wrap="word", font=self.f["n"], bg=CARTAO, padx=10, pady=8)
        caixa.pack(fill="both", expand=True, padx=12, pady=12)
        caixa.focus_set()

        def ok():
            t = caixa.get("1.0", "end").strip()
            if t:
                self.definir_texto(t, "texto colado")
            j.destroy()

        ttk.Button(j, text="Usar este texto", command=ok).pack(pady=(0, 12))

    # ------------------------------------------------------------------ verificação
    def verificar_clique(self) -> None:
        if self.ocupado or not self.texto.strip():
            return
        if contar_palavras(self.texto) < MIN_PALAVRAS:
            messagebox.showwarning("Texto curto", f"O texto é curto demais para verificar. "
                                                  f"Use um trabalho com pelo menos {MIN_PALAVRAS} palavras.")
            return
        self._avisou_offline = False
        if self.online is False:
            self._avisou_offline = True
            messagebox.showwarning("Sem internet", AVISO_OFFLINE)
        self.ocupado = True
        for b in (self.btn_verificar, self.btn_escolher, self.btn_colar):
            b.config(state="disabled")
        self.area_prog.pack(side="left", padx=18)
        self.prog.config(value=2)
        self.lbl_prog.config(text="Preparando...")

        def trabalho(texto=self.texto, nome=self.nome, fila=self.fila, conferir=self.var_conferir.get()):
            try:
                v = verificar(texto, nome, lambda f, m: fila.put(("prog", f, m)), conferir)
                fila.put(("pronto", v))
            except Exception as e:  # noqa: BLE001
                fila.put(("erro", str(e)))

        threading.Thread(target=trabalho, daemon=True).start()

    def _ler_fila(self) -> None:
        try:
            while True:
                msg = self.fila.get_nowait()
                if msg[0] == "rede":
                    self._aplicar_rede(msg[1])
                elif msg[0] == "teste_chave":
                    self._resultado_teste_chave(msg[1])
                elif msg[0] == "prog":
                    self.prog.config(value=msg[1] * 100)
                    self.lbl_prog.config(text=msg[2])
                elif msg[0] == "pronto":
                    self._finalizar()
                    self.verif = msg[1]
                    self._mostrar(msg[1])
                elif msg[0] == "erro":
                    self._finalizar()
                    messagebox.showerror("Algo deu errado", f"Não foi possível concluir a verificação.\n\n{msg[1]}")
        except queue.Empty:
            pass
        self._depois["fila"] = self.after(100, self._ler_fila)

    def _finalizar(self) -> None:
        self.ocupado = False
        self.area_prog.pack_forget()
        for b in (self.btn_verificar, self.btn_escolher, self.btn_colar):
            b.config(state="normal")

    # ------------------------------------------------------------------ resultados
    def _mostrar(self, v: Verificacao) -> None:
        estado, titulo, resumo = veredito_plagio(v)
        self.card_plagio[1].config(text="Plágio:  " + titulo)
        self.card_plagio[2].config(text=resumo)
        self._pintar(self.card_plagio, COR_PLAGIO[estado])

        r = v.referencias
        self.card_refs[1].config(text="Referências:  " + VEREDITO_REFERENCIAS[r.veredito])
        problemas = [i.texto for i in r.itens if i.status != "ok"]
        self.card_refs[2].config(text=" ".join(problemas[:3]) if problemas
                                 else "A lista de referências e as citações do texto estão de acordo.")
        self._pintar(self.card_refs, COR_REFS[r.veredito])

        nota = NOTA_LIMITES
        if v.busca and v.busca.falhas and not v.motivo:
            nota = "Algumas consultas falharam e o resultado pode estar incompleto. " + nota
        self.lbl_nota.config(text=nota)

        self._desenhar_grafico(dados_grafico(v))

        # plágio: fontes, texto marcado e origem de cada trecho
        self.tree_achados.delete(*self.tree_achados.get_children())
        self.achados_na_tela = v.busca.achados if v.busca else []
        for i, a in enumerate(self.achados_na_tela):
            cor = (f"c{i % len(PALETA)}",) if a.palavras else ()
            self.tree_achados.insert("", "end", iid=str(i), tags=cor, values=(
                i + 1, ROTULO_NIVEL[a.nivel], a.fonte, a.titulo, (pct_br(a.pct) + "%") if a.palavras else "-"))
        self._mostrar_trabalho(v)
        self._preencher_iguais(v)
        if self.achados_na_tela:
            primeira = next((i for i, a in enumerate(self.achados_na_tela) if a.palavras), 0)
            self.tree_achados.selection_set(str(primeira))
        else:
            self.lbl_origem.config(text=titulo + "  " + resumo, fg=TINTA)
            self.btn_abrir.config(state="disabled")

        # referências
        partes: list[tuple[str, str]] = []
        for it in r.itens:
            partes += [(f" {ICONE[it.status]}  ", it.status), (it.texto + "\n", "")]
        if r.citadas_sem_referencia:
            partes += [("\nCitadas no texto, mas ausentes da lista: ", "negrito"),
                       (", ".join(r.citadas_sem_referencia) + "\n", "")]
        if r.aspas_sem_fonte:
            partes += [("\nCitação direta sem fonte: ", "negrito"), (r.aspas_sem_fonte[0] + "\n", "")]
        self._escrever(self.txt_refs, partes)
        self.tree_refs.delete(*self.tree_refs.get_children())
        for i, e in enumerate(r.entradas):
            ex = v.existencia[i] if v.existencia and i < len(v.existencia) else None
            formato = "OK" if not e.problemas else f"{len(e.problemas)} problema(s)"
            self.tree_refs.insert("", "end", iid=str(i), values=(i + 1, e.texto[:140], formato,
                                                                 SITUACAO[ex.situacao] if ex else "Sem internet"))
        self._escrever(self.txt_ref_detalhe, [("Selecione uma referência para ver os detalhes.", "suave")])

        self.btn_salvar.config(state="normal")
        self.abas.select(0)
        if v.motivo == "offline":
            if not self._avisou_offline:
                messagebox.showwarning("Sem internet", MOTIVOS["offline"] + "\n\nAs referências foram analisadas normalmente.")
        elif v.motivo in ("rede", "limite", "chave"):
            messagebox.showwarning("Busca incompleta", MOTIVOS[v.motivo])

    def _mostrar_trabalho(self, v: Verificacao) -> None:
        t = self.txt_trabalho
        t.config(state="normal")
        t.delete("1.0", "end")
        t.insert("1.0", v.texto)
        for tag in t.tag_names():
            if tag.startswith("fonte_"):
                t.tag_delete(tag)
        trechos = v.busca.trechos if v.busca else []
        for i in sorted({x.fonte for x in trechos}):
            tag = f"fonte_{i}"
            t.tag_configure(tag, background=PALETA[i % len(PALETA)], foreground=TINTA)
            t.tag_bind(tag, "<Button-1>", lambda e, k=i: self._clicou_trecho(k))
            t.tag_bind(tag, "<Double-Button-1>", lambda e, k=i: self._abrir_fonte(k))
            t.tag_bind(tag, "<Enter>", lambda e: t.config(cursor="hand2"))
            t.tag_bind(tag, "<Leave>", lambda e: t.config(cursor=""))
        for x in trechos:
            t.tag_add(f"fonte_{x.fonte}", f"1.0+{x.ini}c", f"1.0+{x.fim}c")
        t.config(state="disabled")
        t.yview_moveto(0)

    def _descricao_fonte(self, i: int) -> str:
        a = self.achados_na_tela[i]
        partes = [a.titulo, f"({a.fonte}" + (f", {a.ano}" if a.ano else "") + ")"]
        if a.autores and a.fonte != "Wikipédia":
            partes.append("de " + a.autores)
        return " ".join(partes)

    def _clicou_trecho(self, i: int) -> None:
        if self.tree_achados.selection() != (str(i),):
            self.tree_achados.selection_set(str(i))
        a = self.achados_na_tela[i]
        self.lbl_origem.config(text="Este trecho vem de: " + self._descricao_fonte(i) +
                                    ("\nDê dois cliques no trecho para abrir a fonte." if a.link else ""), fg=TINTA)

    def _selecionar_fonte(self, _=None) -> None:
        sel = self.tree_achados.selection()
        if not sel:
            return
        i = int(sel[0])
        a = self.achados_na_tela[i]
        self.btn_abrir.config(state="normal" if a.link else "disabled")
        if a.palavras:
            aviso = (f"{pct_br(a.pct)}% do trabalho ({a.palavras} palavras) vem desta fonte" +
                     (" (comparado só pelo resumo)" if a.origem_texto == "resumo" else "") + ".")
            self.lbl_origem.config(text=self._descricao_fonte(i) + "\n" + aviso, fg=TINTA)
            faixa = self.txt_trabalho.tag_ranges(f"fonte_{i}")
            if faixa:
                self.txt_trabalho.see(faixa[0])
        else:
            self.lbl_origem.config(text=self._descricao_fonte(i) + "\nTrabalho sobre o mesmo assunto, sem trechos copiados.",
                                   fg=SUAVE)

    def _preencher_iguais(self, v: Verificacao) -> None:
        self.tree_iguais.delete(*self.tree_iguais.get_children())
        for t in (self.txt_igual_meu, self.txt_igual_fonte):
            self._escrever(t, [])
        self.lbl_igual_info.config(text="")
        self.lbl_trecho.config(text="")
        self.trechos_sel = []
        self.btn_abrir_igual.config(state="disabled")
        achados = v.busca.achados if v.busca else []
        com_plagio = [i for i, a in enumerate(achados) if a.palavras]
        if not com_plagio:
            _, titulo, resumo = veredito_plagio(v)
            self.lbl_iguais.config(text=titulo + "  " + resumo + "\nNenhum trabalho igual ao seu foi encontrado para mostrar aqui.")
            return
        self.lbl_iguais.config(text=f"Encontramos {len(com_plagio)} trabalho(s) com trechos iguais ao seu. Selecione um para ver, "
                                    "lado a lado, o que foi copiado. Use os botões para pular de trecho em trecho.")
        for k, i in enumerate(com_plagio, 1):
            a = achados[i]
            qtd = sum(1 for x in v.busca.trechos if x.fonte == i)
            self.tree_iguais.insert("", "end", iid=str(i), tags=(f"c{i % len(PALETA)}",),
                                    values=(k, a.titulo, a.fonte, pct_br(a.pct) + "%", qtd))
        self.tree_iguais.selection_set(str(com_plagio[0]))

    def _selecionar_igual(self, _=None) -> None:
        sel = self.tree_iguais.selection()
        if not sel or not self.verif or not self.verif.busca:
            return
        i = int(sel[0])
        a = self.verif.busca.achados[i]
        cor = PALETA[i % len(PALETA)]
        self.trechos_sel = [t for t in self.verif.busca.trechos if t.fonte == i]
        self.nav_i = 0
        nota = ""
        if a.origem_texto == "resumo":
            nota = "\nSó o resumo deste trabalho pôde ser lido; o texto completo está no site da fonte."
        self.lbl_igual_info.config(text=f"{a.titulo}\n{a.tipo}  |  {a.ano or 's/d'}  |  {a.autores}  |  fonte: {a.fonte}  |  "
                                        f"{pct_br(a.pct)}% do seu trabalho vem daqui" + nota, wraplength=self.winfo_width() - 60)
        self.btn_abrir_igual.config(state="normal" if a.link else "disabled")

        # lado esquerdo: o seu trabalho, só com os trechos desta fonte marcados
        t = self.txt_igual_meu
        t.config(state="normal")
        t.delete("1.0", "end")
        t.insert("1.0", self.verif.texto)
        for tag in t.tag_names():
            if tag.startswith("trecho_") or tag in ("marca", "atual"):
                t.tag_delete(tag)
        t.tag_configure("marca", background=cor, foreground=TINTA)
        for k, x in enumerate(self.trechos_sel):
            t.tag_add("marca", f"1.0+{x.ini}c", f"1.0+{x.fim}c")
            t.tag_add(f"trecho_{k}", f"1.0+{x.ini}c", f"1.0+{x.fim}c")
            t.tag_bind(f"trecho_{k}", "<Button-1>", lambda e, n=k: self._ir_trecho(n))
            t.tag_bind(f"trecho_{k}", "<Enter>", lambda e: t.config(cursor="hand2"))
            t.tag_bind(f"trecho_{k}", "<Leave>", lambda e: t.config(cursor=""))
        t.tag_configure("atual", background="#FFD54A", foreground=TINTA, underline=True)
        t.config(state="disabled")

        # lado direito: o trabalho encontrado, com o que foi copiado marcado
        f = self.txt_igual_fonte
        f.config(state="normal")
        f.delete("1.0", "end")
        for tag in ("marca", "atual"):
            f.tag_delete(tag)
        if a.texto_fonte.strip():
            f.insert("1.0", a.texto_fonte)
            f.tag_configure("marca", background=cor, foreground=TINTA)
            for ini, fim in a.marcas_fonte:
                f.tag_add("marca", f"1.0+{ini}c", f"1.0+{fim}c")
            f.tag_configure("atual", background="#FFD54A", foreground=TINTA, underline=True)
        else:
            f.insert("1.0", "O texto deste trabalho não pôde ser lido pelo programa.\n\nAbra o trabalho no navegador "
                            "(botão acima). Trechos do seu texto que foram encontrados nele:\n\n" +
                            "\n".join("  “" + fr + "”" for fr in a.frases))
        f.config(state="disabled")
        self._ir_trecho(0)

    def _ir_trecho(self, k: int) -> None:
        if not self.trechos_sel:
            self.lbl_trecho.config(text="")
            return
        self.nav_i = k % len(self.trechos_sel)
        x = self.trechos_sel[self.nav_i]
        self.lbl_trecho.config(text=f"Trecho {self.nav_i + 1} de {len(self.trechos_sel)}")
        for t, ini, fim in ((self.txt_igual_meu, x.ini, x.fim),
                            (self.txt_igual_fonte, x.fonte_ini, x.fonte_fim)):
            t.tag_remove("atual", "1.0", "end")
            if ini >= 0 and "atual" in t.tag_names():
                t.tag_add("atual", f"1.0+{ini}c", f"1.0+{fim}c")
                t.tag_raise("atual")
                t.see(f"1.0+{ini}c")

    def _abrir_igual(self) -> None:
        sel = self.tree_iguais.selection()
        if sel:
            self._abrir_fonte(int(sel[0]))

    def _abrir_fonte(self, i: int) -> None:
        if self.achados_na_tela[i].link:
            webbrowser.open(self.achados_na_tela[i].link)

    def abrir_achado(self) -> None:
        sel = self.tree_achados.selection()
        if sel and self.achados_na_tela[int(sel[0])].link:
            webbrowser.open(self.achados_na_tela[int(sel[0])].link)

    def _detalhe_ref(self, _=None) -> None:
        sel = self.tree_refs.selection()
        if not sel or not self.verif:
            return
        i = int(sel[0])
        e = self.verif.referencias.entradas[i]
        partes: list[tuple[str, str]] = [(e.texto + "\n", "")]
        for p in e.problemas:
            partes.append((f" ✖  {p}\n", "problema"))
        if not e.problemas:
            partes.append((" ✔  Formato conforme o esperado.\n", "ok"))
        if self.verif.existencia and i < len(self.verif.existencia):
            ex = self.verif.existencia[i]
            if ex.situacao == "encontrada":
                partes.append((f" ✔  Encontrada na internet: {ex.titulo}\n", "ok"))
            elif ex.situacao == "nao_encontrada":
                partes.append((" !  Não encontrada no catálogo online. Livros, leis e sites costumam não estar nele, "
                               "então isso não prova que a referência seja falsa.\n", "atencao"))
        self._escrever(self.txt_ref_detalhe, partes)

    # ------------------------------------------------------------------ arquivos do usuário
    def adicionar_locais(self) -> None:
        caminhos = filedialog.askopenfilenames(
            title="Escolha os arquivos para comparar",
            filetypes=[("Documentos", "*.pdf *.docx *.txt *.rtf *.odt"), ("Todos", "*.*")])
        erros = []
        for c in caminhos:
            try:
                self.arquivos_locais.append((Path(c).name, leitor.ler_arquivo(c)))
            except leitor.ErroLeitura as e:
                erros.append(f"{Path(c).name}: {e}")
        self._atualizar_lista_locais()
        if erros:
            messagebox.showwarning("Alguns arquivos não foram lidos", "\n\n".join(erros))

    def remover_local(self) -> None:
        sel = self.lista_locais.curselection()
        if sel:
            del self.arquivos_locais[sel[0]]
            self._atualizar_lista_locais()

    def _atualizar_lista_locais(self) -> None:
        self.lista_locais.delete(0, "end")
        for nome, t in self.arquivos_locais:
            self.lista_locais.insert("end", f"{nome}   ({contar_palavras(t)} palavras)")
        self._atualizar_comparar()

    def _atualizar_comparar(self) -> None:
        pronto = bool(self.texto.strip()) and bool(self.arquivos_locais)
        self.btn_comparar.config(state="normal" if pronto else "disabled")

    def comparar_locais(self) -> None:
        self.locais = sorted((comparacao.comparar(self.texto, n, t) for n, t in self.arquivos_locais),
                             key=lambda x: -x.cobertura)
        self.tree_locais.delete(*self.tree_locais.get_children())
        for i, x in enumerate(self.locais):
            self.tree_locais.insert("", "end", iid=str(i),
                                    values=(x.nome, f"{x.cobertura:.1f}%", ROTULO_RISCO[x.risco]))
        if self.locais:
            self.tree_locais.selection_set("0")

    def _detalhe_local(self, _=None) -> None:
        sel = self.tree_locais.selection()
        if not sel:
            return
        x = self.locais[int(sel[0])]
        partes: list[tuple[str, str]] = []
        for palavra, marcada in zip(x.palavras, x.marcado):
            partes.append((palavra + " ", "marca_" + x.risco if marcada else ""))
        self._escrever(self.txt_local, partes)

    # ------------------------------------------------------------------ configurações
    def _salvar_cfg(self, **mudancas) -> None:
        self.cfg.update(mudancas)
        try:
            config.salvar(self.cfg)
        except OSError:
            pass

    def abrir_config(self) -> None:
        j = tk.Toplevel(self)
        j.title("Configurações")
        j.configure(bg=PAPEL, padx=20, pady=16)
        j.resizable(False, False)
        j.transient(self)
        tk.Label(j, text="Chave do OpenAlex (opcional)", font=self.f["g"], bg=PAPEL, fg=TINTA).pack(anchor="w")
        tk.Label(j, justify="left", wraplength=480, font=self.f["n"], bg=PAPEL, fg=SUAVE, text=(
            "O Pega Plágio procura trabalhos no catálogo OpenAlex. Sem chave, o limite é de poucas verificações por dia. "
            "Com uma chave gratuita o limite fica cerca de 10 vezes maior.\n\n"
            "Como conseguir: crie uma conta gratuita em openalex.org, abra as configurações de API e copie a chave "
            "para o campo abaixo.")).pack(anchor="w", pady=(4, 10))
        var = tk.StringVar(value=self.cfg["openalex_chave"])
        campo = ttk.Entry(j, textvariable=var, width=56, show="•")
        campo.pack(anchor="w")
        mostrar = tk.BooleanVar(value=False)
        tk.Checkbutton(j, text="Mostrar a chave", variable=mostrar, bg=PAPEL, font=self.f["n"], activebackground=PAPEL,
                       command=lambda: campo.config(show="" if mostrar.get() else "•")).pack(anchor="w", pady=(2, 10))
        botoes = tk.Frame(j, bg=PAPEL)
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Abrir o site do OpenAlex",
                   command=lambda: webbrowser.open("https://openalex.org/settings/api")).pack(side="left")
        ttk.Button(botoes, text="Testar a chave", command=lambda: self._testar_chave(var.get())).pack(side="left", padx=8)

        def salvar():
            chave = var.get().strip()
            self._salvar_cfg(openalex_chave=chave)
            busca.definir_chave(chave)
            j.destroy()

        ttk.Button(botoes, text="Salvar", command=salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=j.destroy).pack(side="right", padx=8)
        campo.focus_set()

    def _testar_chave(self, chave: str) -> None:
        if not chave.strip():
            messagebox.showinfo("Testar a chave", "Cole a chave no campo antes de testar.")
            return
        fila = self.fila

        def trabalho():
            try:
                busca.testar_chave(chave.strip())
                fila.put(("teste_chave", "ok"))
            except rede.ErroRede as e:
                fila.put(("teste_chave", e.codigo))

        threading.Thread(target=trabalho, daemon=True).start()

    def _resultado_teste_chave(self, codigo: str) -> None:
        if codigo == "ok":
            messagebox.showinfo("Testar a chave", "A chave foi aceita pelo OpenAlex.")
        elif codigo == "chave":
            messagebox.showwarning("Testar a chave", "O OpenAlex não aceitou esta chave. Confira se copiou inteira.")
        elif codigo == "limite":
            messagebox.showwarning("Testar a chave", "A chave foi reconhecida, mas o limite de buscas de hoje já acabou.")
        else:
            messagebox.showwarning("Testar a chave", "Não foi possível falar com o OpenAlex. Confira a internet.")

    # ------------------------------------------------------------------ relatório
    def salvar(self) -> None:
        if not self.verif:
            return
        caminho = filedialog.asksaveasfilename(
            title="Salvar relatório", defaultextension=".txt", initialfile="relatorio.txt",
            filetypes=[("Texto", "*.txt")])
        if caminho:
            Path(caminho).write_text(montar(self.verif, self.locais), encoding="utf-8")
            messagebox.showinfo("Relatório salvo", f"O relatório foi salvo em:\n{caminho}")


def iniciar() -> None:
    App().mainloop()
