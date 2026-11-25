import sys, time, pathlib, tempfile, tkinter as tk
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tkinter import messagebox, ttk
import servidor_falso as sf
from plagio import busca, config
caixas = []
for nome in ("showwarning", "showerror", "showinfo"):
    setattr(messagebox, nome, lambda t, m, _n=nome, **k: caixas.append((_n, t, m)))
srv, porta = sf.iniciar(); sf.apontar_para(porta); sf.H.modo = "exigir_chave"
config.CAMINHO = pathlib.Path(tempfile.mkdtemp()) / "cfg.json"
from plagio.interface import App
app = App(); app.geometry("1060x800+0+0")
def esperar(c, lim=15):
    t = time.time()
    while time.time() - t < lim:
        app.update()
        if c(): return True
        time.sleep(0.02)
esperar(lambda: app.online is not None)
app.abrir_config(); app.update()
j = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][0]
def achar(w, cls, texto=None):
    for f in w.winfo_children():
        if isinstance(f, cls) and (texto is None or f.cget("text") == texto): return f
        r = achar(f, cls, texto)
        if r: return r
campo = achar(j, ttk.Entry)
campo.insert(0, "RUIM"); app._testar_chave("RUIM"); esperar(lambda: caixas)
print("chave ruim ->", caixas[-1][0], "|", caixas[-1][2][:60]); caixas.clear()
campo.delete(0, "end"); campo.insert(0, "BOA"); app._testar_chave("BOA"); esperar(lambda: caixas)
print("chave boa  ->", caixas[-1][0], "|", caixas[-1][2][:60])
app.update(); time.sleep(.3); app.update()
from PIL import ImageGrab
x, y, w, h = j.winfo_rootx(), j.winfo_rooty(), j.winfo_width(), j.winfo_height()
ImageGrab.grab(bbox=(x, y, x + w, y + h)).save("/tmp/dialogo.png")
achar(j, ttk.Button, "Salvar").invoke(); app.update()
print("depois de salvar -> chave em uso:", busca.CHAVE_OPENALEX, "| arquivo:", config.carregar()["openalex_chave"], "| janela fechou:", not j.winfo_exists())
app.var_conferir.set(False); app.update()
print("caixa desmarcada -> salvo como:", config.carregar()["conferir_referencias"])
app._fechar()
# reabrir o programa: lembra das escolhas?
app2 = App(); app2.update()
print("reabrindo -> chave:", busca.CHAVE_OPENALEX, "| caixa marcada:", app2.var_conferir.get())
app2.geometry("1060x800+0+0"); app2.update(); time.sleep(.3); app2.update()
ImageGrab.grab(bbox=(0, 0, 1060, 330)).save("/tmp/principal.png"); app2._fechar()
