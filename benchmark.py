import time
import tracemalloc
from plagio.comparacao import distancia_levenshtein, calcular_similaridade_hibrida
from plagio.texto import normalizar_e_tokenizar

# 1. Prova de Exatidão Matemática (Caso de Teste Controlado)
frase_a = "a engenharia de software exige rigor"
frase_b = "a engenharia de softwares exige rigor"  # 1 inserção ('s')

dist = distancia_levenshtein(frase_a, frase_b)
tokens_a = normalizar_e_tokenizar(frase_a)
tokens_b = normalizar_e_tokenizar(frase_b)
sim_total = calcular_similaridade_hibrida(frase_a, frase_b, tokens_a, tokens_b)

print("=== PROVA MATEMÁTICA ===")
print(f"Distância de Levenshtein esperada: 1 | Obtida: {dist}")
print(f"Tokens A: {tokens_a}")
print(f"Tokens B: {tokens_b}")
print(f"Similaridade Híbrida obtida: {sim_total:.2%}\n")

# 2. Prova de Desempenho (Tempo e Memória RAM)
print("=== BENCHMARK DE TEMPO E MEMÓRIA ===")
base_texto = "O desenvolvimento de software deterministico garante transparencia e auditoria. "

for multiplicador in [10, 50, 150]:  # ~100, ~500 e ~1.500 palavras
    texto_teste = base_texto * multiplicador
    texto_comp = texto_teste.replace("transparencia", "clareza")
    qtd_palavras = len(texto_teste.split())

    tracemalloc.start()
    inicio = time.perf_counter()

    t_a = normalizar_e_tokenizar(texto_teste)
    t_b = normalizar_e_tokenizar(texto_comp)
    resultado = calcular_similaridade_hibrida(texto_teste, texto_comp, t_a, t_b)

    fim = time.perf_counter()
    _, pico_memoria = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    tempo_ms = (fim - inicio) * 1000
    memoria_kb = pico_memoria / 1024

    print(f"Volume: {qtd_palavras} palavras | Tempo: {tempo_ms:.2f} ms | Pico RAM: {memoria_kb:.2f} KB | Sim: {resultado:.2%}")
