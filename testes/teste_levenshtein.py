"""Confere o Levenshtein rápido (Myers) contra a tabela tradicional, em milhares de casos."""
import pathlib, random, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from plagio.comparacao import calcular_similaridade_hibrida, distancia_levenshtein
from plagio.texto import normalizar_e_tokenizar


def referencia(a, b):                       # tabela tradicional, só para conferir
    ant = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            atual.append(min(ant[j] + 1, atual[j - 1] + 1, ant[j - 1] + (ca != cb)))
        ant = atual
    return ant[-1]


fixos = [("", ""), ("", "abc"), ("abc", ""), ("abc", "abc"), ("kitten", "sitting"), ("flaw", "lawn"),
         ("a", "b"), ("ação", "acao"), ("software", "softwares"), ("abcdef", "azced"), ("aaaa", "aa")]
for a, b in fixos:
    assert distancia_levenshtein(a, b) == referencia(a, b), (a, b)
print("casos fixos ok:", len(fixos), "| kitten/sitting =", distancia_levenshtein("kitten", "sitting"))

random.seed(7)
for alfabeto, n in (("ab", 3000), ("abcdefghij àéõç", 3000), ("ab", 300)):
    for _ in range(n):
        a = "".join(random.choice(alfabeto) for _ in range(random.randint(0, 40 if n > 300 else 150)))
        b = "".join(random.choice(alfabeto) for _ in range(random.randint(0, 40 if n > 300 else 150)))
        assert distancia_levenshtein(a, b) == referencia(a, b), (a, b)
        assert distancia_levenshtein(a, b) == distancia_levenshtein(b, a)
print("6300 pares aleatórios: o rápido e a tabela tradicional dão sempre o mesmo número")

# propriedades da similaridade híbrida
t = lambda x: normalizar_e_tokenizar(x)
h = lambda a, b: calcular_similaridade_hibrida(a, b, t(a), t(b))
assert h("o gato dorme", "o gato dorme") == 1.0
assert h("", "") == 0.0
assert 0.0 <= h("abc def", "xyz uvw") < 0.3
assert h("a engenharia de software exige rigor", "a engenharia de softwares exige rigor") > 0.8
print(f"similaridade híbrida: idênticos = 100%, vazios = 0%, textos sem relação = {100 * h('abc def', 'xyz uvw'):.1f}%")
