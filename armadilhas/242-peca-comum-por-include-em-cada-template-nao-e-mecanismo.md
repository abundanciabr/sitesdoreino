---
schema_version: 2
armadilha: 242
estado: documentada
degrau: 5
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: nenhum portão do repositório sabe o que é "peça que devia estar em toda página" — a régua é da célula. O que existe é o MOLDE do guarda, escrito aqui, e as duas implementações dele em `services/funil/tests/test_rodape.py` e `services/forum/tests/test_rodape.py`
---

# Peça que tem de aparecer "em todas as páginas": `{% include %}` por template não é mecanismo

**Sintoma.** A peça comum (rodapé, cabeçalho, faixa de aviso, banner de
consentimento) aparece em todas as telas no dia da entrega, e some da PRIMEIRA
tela nova. Ninguém percebe: a página abre normalmente, nenhum teste fica
vermelho, nenhum portão reclama. O buraco só aparece quando alguém olha o site
com os próprios olhos, semanas depois.

**Causa.** `{% extends %}` + um `{% include "peca.html" %}` escrito à mão em
cada template faz a frase "em todas as páginas" depender de alguém lembrar de
incluir a peça. Lembrar não é mecanismo, e é a mesma doença da Classe 8 do
`PLANO-MESTRE-ROBOS-SEM-COLISAO.md` (mapa mantido à mão envelhece em silêncio):
o que envelhece aqui não é um mapa, é a cobertura da peça.

**Solução, em duas metades — e as duas são necessárias:**

1. **Quem DECIDE é um processador de contexto; quem DESENHA é o molde.** Um
   módulo da célula (`apps/core/<peca>.py`) devolve o dicionário da peça, o
   `settings.py` o registra em `context_processors`, e o template-base desenha
   dentro de um `{% if %}`. Tela nova herda a peça sem tocar em nada.
2. **O guarda varre o urlconf REAL, não uma lista escrita à mão.** Sem ele a
   primeira metade também envelhece: alguém acrescenta uma rota, ninguém decide
   nada sobre a peça, e o silêncio vira resposta. O molde:

```python
nomes = {p.name for p in get_resolver().url_patterns if getattr(p, "name", None)}
sem_peca = {nome for nome in nomes if variante_da_rota(nome) is None}
assert sem_peca == set(ROTAS_SEM_PAGINA) & nomes   # sem peça só por decisão ESCRITA
for nome in nomes - sem_peca:
    assert variante_da_rota(nome) in VARIANTES     # o resto herda o padrão
```

A regra que o molde impõe: **silêncio significa o padrão, nunca "sem a peça"**.
Rota que alguém quis sem a peça precisa estar dita por nome.

**Duas armadilhas menores que vêm junto, e custam uma rodada cada:**

- **A prova é sobre o CORPO RENDERIZADO, nunca sobre a tabela de regras.** Uma
  tabela certa com um molde que ignora a decisão passa num teste que só lê a
  tabela. É a lição da `armadilhas/087`: vazamento não escolhe a tag que você
  previu.
- **Numa célula que serve o estilo por rota própria (`armadilhas/083`), a classe
  nova no HTML sem a regra no CSS é a peça sem forma, e nada fica vermelho.** O
  guarda do estilo pergunta ao SERVIDOR, não ao disco. E cuidado: essa rota
  costuma devolver `FileResponse`, que não tem `.content` — pedir por ele
  levanta `AttributeError` e deixa o teste vermelho por INSTRUMENTO, não por
  defeito (INV-CI01). Use `streaming_content`.

**A metade que quase se perde no caminho: o template-base é compartilhado com
quem não quer a peça.** No `funil`, a mesma `base_mobile.html` serve os domínios
monolíngues, cuja saída é comparada BYTE A BYTE por um golden. A peça (e o
estilo dela) nasce dentro do `{% if %}`, com as tags coladas no fim da linha
anterior (`§4.14`); solta, ela derruba o golden sem ter nada a ver com ele.

**Origem:** 31/08/2026, TAR-070 e TAR-081 — o rodapé do site (PR #705) e o do
fórum (PR #711), pedidos pelo mantenedor no mesmo dia. As duas células nasceram
com a mesma forma de propósito: a etapa seguinte (o mantenedor editando os
textos no painel) vai mandar nas duas pelo mesmo caminho.
