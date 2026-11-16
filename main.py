"""Pega Plágio: programa de computador que procura plágio e confere as referências (sem IA)."""
import sys

try:
    from plagio.interface import iniciar
except ImportError as erro:  # tkinter ausente (comum no Linux)
    sys.exit("Não foi possível abrir a janela do programa: " + str(erro) +
             "\nNo Linux, instale com: sudo apt install python3-tk")

if __name__ == "__main__":
    iniciar()
