import sys, time, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tkinter import messagebox
import servidor_falso as sf
from plagio import rede
from plagio.interface import App

caixas = []
for nome in ("showwarning", "showerror", "showinfo"):
    setattr(messagebox, nome, lambda t, m, _n=nome, **k: caixas.append((_n, t, m)))
srv, porta = sf.iniciar(); sf.apontar_para(porta)
base = pathlib.Path(__file__).resolve().parent

def esperar(app, cond, limite=40):
    t = time.time()
    while time.time() - t < limite:
        app.update()
        if cond(): return True
        time.sleep(0.02)
    return False

def foto(app, arq):
    app.update(); time.sleep(0.3); app.update()
    from PIL import ImageGrab
    ImageGrab.grab(bbox=(0, 0, 1060, 800)).save(arq)

def cenario(nome, texto, online=True, modo="copia"):
    sf.H.modo = modo
    rede.HOSTS_TESTE = [("127.0.0.1", porta if online else 9)]
    caixas.clear()
    app = App(); app.geometry("1060x800+0+0")
    esperar(app, lambda: app.online is not None, 10)
    app.definir_texto(texto, "trabalho.txt"); app.verificar_clique()
    ok = esperar(app, lambda: app.verif is not None and not app.ocupado)
    c = app.canvas
    textos = [c.itemcget(i, "text") for i in c.find_all() if c.type(i) == "text"]
    print(f"--- {nome} --- terminou: {ok}")
    print("plágio :", app.card_plagio[1].cget("text"))
    print("refs   :", app.card_refs[1].cget("text"))
    print("gráfico:", textos, "|", app.lbl_g_titulo.cget("text"))
    print("legenda:", app.lbl_g_a.cget("text"), "||", app.lbl_g_nota.cget("text"))
    print("fontes :", [app.tree_achados.item(i, "values")[1:3] + (app.tree_achados.item(i, "values")[4],) for i in app.tree_achados.get_children()])
    print("trechos marcados:", sum(len(app.txt_trabalho.tag_ranges(t)) // 2 for t in app.txt_trabalho.tag_names() if t.startswith("fonte_")))
    print("avisos :", [(x[0], x[1]) for x in caixas])
    return app

qual = sys.argv[1]
if qual == "online":
    app = cenario("COM PLÁGIO", sf.trabalho_exemplo())
    foto(app, "/tmp/g_resumo_plagio.png")
    app.abas.select(1); app.update()
    app._clicou_trecho(1)
    print("clique no trecho ->", app.lbl_origem.cget("text").replace("\n", " | "))
    foto(app, "/tmp/g_plagio.png")
    # --- aba "Trabalhos iguais"
    app.abas.select(2); app.update()
    print("aba:", app.abas.tab(app.abas.select(), "text"))
    print("trabalhos iguais:", [app.tree_iguais.item(i, "values")[1:] for i in app.tree_iguais.get_children()])
    sel = app.tree_iguais.selection()[0]
    marcas = lambda t: len(t.tag_ranges("marca")) // 2
    print("selecionado:", sel, "| marcas no seu trabalho:", marcas(app.txt_igual_meu), "| marcas no trabalho encontrado:", marcas(app.txt_igual_fonte))
    print("contador:", app.lbl_trecho.cget("text"))
    atual = lambda t: [t.get(a_, b_)[:45] for a_, b_ in zip(t.tag_ranges("atual")[::2], t.tag_ranges("atual")[1::2])]
    print("trecho atual (seu):", atual(app.txt_igual_meu), "| (fonte):", atual(app.txt_igual_fonte))
    app.btn_prox.invoke(); app.update()
    print("depois de 'Próximo':", app.lbl_trecho.cget("text"), atual(app.txt_igual_meu), atual(app.txt_igual_fonte))
    foto(app, "/tmp/g_iguais.png")
    outro = [i for i in app.tree_iguais.get_children() if i != sel][0]
    app.tree_iguais.selection_set(outro); app.update()
    print("outro trabalho:", app.tree_iguais.item(outro, "values")[1][:40], "| marcas:", marcas(app.txt_igual_meu), marcas(app.txt_igual_fonte))
    app._fechar()
elif qual == "limpo":
    app = cenario("SEM PLÁGIO", (base / "exemplo_ruim.txt").read_text(encoding="utf-8"))
    foto(app, "/tmp/g_resumo_limpo.png")
    print("aba iguais (sem plágio):", app.lbl_iguais.cget("text").replace("\n", " | ")[:140], "| linhas:", len(app.tree_iguais.get_children()))
    app._fechar()
elif qual == "offline":
    app = cenario("SEM INTERNET", (base / "exemplo_ruim.txt").read_text(encoding="utf-8"), online=False)
    foto(app, "/tmp/g_offline.png"); app._fechar()
else:
    app = cenario("LIMITE", sf.trabalho_exemplo(), modo="limite"); app._fechar()
