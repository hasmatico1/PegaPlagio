import sys, pathlib, tempfile, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import servidor_falso as sf
from plagio import busca, config, rede
from plagio.verificacao import verificar, veredito_plagio
srv, porta = sf.iniciar(); sf.apontar_para(porta)
T = sf.trabalho_exemplo()
def n_openalex(): return sum(1 for c in sf.H.consultas if c.startswith("/openalex"))
def rodar(modo, chave="", conferir=True):
    sf.H.modo = modo; sf.H.consultas.clear(); busca.definir_chave(chave)
    v = verificar(T, "t.txt", None, conferir)
    return v

print("1) códigos de erro do servidor")
for modo in ("limite", "limite409", "exigir_chave"):
    sf.H.modo = modo; busca.definir_chave("")
    try: busca._openalex("x"); r = "sem erro"
    except rede.ErroRede as e: r = e.codigo
    print(f"   {modo:13} -> {r}")

print("2) sem chave quando o OpenAlex exige")
v = rodar("exigir_chave")
print("   motivo:", v.motivo, "| fontes achadas:", [(a.fonte, a.palavras) for a in v.busca.achados if a.palavras], "| veredito:", veredito_plagio(v)[1][:50])
print("   explicação inclui aviso:", "incompleta" in veredito_plagio(v)[2])

print("3) com chave correta")
v = rodar("exigir_chave", "BOA")
print("   motivo:", v.motivo, "| fontes achadas:", sorted(a.fonte for a in v.busca.achados if a.palavras), "| chave enviada:", any("api_key=BOA" in c for c in sf.H.consultas))

print("4) conferência opcional das referências (buscas no OpenAlex)")
v1 = rodar("copia", "", True);  n1 = n_openalex(); e1 = v1.existencia is not None
v2 = rodar("copia", "", False); n2 = n_openalex(); e2 = v2.existencia is not None
print(f"   ligada: {n1} buscas, conferiu={e1}  |  desligada: {n2} buscas, conferiu={e2}")

print("5) arquivo de configuração")
d = pathlib.Path(tempfile.mkdtemp()); config.CAMINHO = d / "pasta" / "config.json"
print("   sem arquivo:", config.carregar())
config.salvar({"openalex_chave": "ABC123", "conferir_referencias": False})
print("   salvo e lido:", config.carregar())
config.CAMINHO.write_text("{ quebrado", encoding="utf-8"); print("   arquivo quebrado -> padrão:", config.carregar()["conferir_referencias"])
