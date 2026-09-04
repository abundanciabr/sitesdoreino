---
schema_version: 2
armadilha: 325
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: o sintoma desta falha é a AUSÊNCIA de vermelho, e não uma saída que se possa casar por expressão regular. O que a cura exige é um gesto (mutar a peça que o guarda diz proteger e ver se ele cai), e não existe portão barato que prove que alguém o fez. Por isso não há sinal também - não há texto a casar quando nada falha.
---

# 325 — O guarda que aponta para a peça errada passa por acidente, e a mutação é quem denuncia

**Sintoma.** Um teste-guarda está verde, o nome dele descreve exatamente a
promessa certa, a docstring explica bem por que a promessa importa, e ele **não
mede nada**. Nenhuma ferramenta acusa: cobertura conta a linha como coberta, a
suíte fica verde, e a revisão do PR lê o nome do teste e concorda com ele.

**A causa, em uma frase:** o guarda foi apontado para o lugar onde a promessa é
VISÍVEL, e não para o lugar onde ela é FEITA VALER.

## Caso 1 — o teste que media o molde (04/09/2026, TAR-078, PR #1016)

A tela `/admin/escola/jornadas/` mostra quem está dentro de uma sequência de
mensagens. A `mensageria` não guarda nome, e-mail nem telefone de ninguém
(invariante 1 do contrato congelado), e a tela tem de mostrar só o id opaco. O
guarda escrito para isso fazia o óbvio:

```python
# a porta manda campos a mais, como mandaria no dia em que alguém os
# acrescentasse do outro lado
respx.get(...).mock(... json={... "nome": "Maria de Tal", "email": "maria@exemplo.com"})
html = _texto(cliente.get(...))
for vazamento in ("Maria de Tal", "maria@exemplo.com"):
    assert vazamento not in html
```

Verde. E continuou verde quando a mutação deliberada enfiou
`{{ i.nome }} {{ i.email }}` dentro do molde.

O guarda apontava para o MOLDE, e quem protege o dado não é o molde: é a lista
fechada de campos que a view monta antes de entregá-la ao template. O que não
entra naquele dicionário **não existe** para o molde, então nenhuma mutação de
template consegue vazar coisa nenhuma. O teste media um caminho que já era
impossível — e teria continuado verde para sempre, inclusive no dia em que
alguém trocasse a lista fechada por um `{**inscricao}` e abrisse o vazamento de
verdade, porque nesse dia o MOLDE continuaria sem pedir o campo.

**Solução:** apontar para a peça que faz valer a promessa.

```python
linha = _linha_de_inscricao({... "nome": "Maria de Tal", "email": "..."})
assert set(linha) == {"inscricao_id", "destinatario_id", "estado", ...}
```

Com isso, a mutação de UMA linha (`"motivo_de_saida": ...` virando
`**inscricao,`) ficou vermelha, como devia.

## Caso 2 — a PROVA DE FORA que prova a porta, e não a rota

Descoberto na mesma tarefa, e é o mais perigoso dos dois porque está escrito em
despacho: a prova de fora pedida para toda tela nova da célula `admin` é *"o
código HTTP cru de `https://meshcraft.top/admin/<rota>/` — 302 para o login é o
esperado, o crachá vem antes"*.

O 302 é real e é bom sinal. Mas ele **não prova que a rota existe**, porque a
porta responde ANTES do roteamento. Medido em 04/09/2026, com a tela ainda não
publicada:

```
escola/jornadas/         302 -> /entrar/google?next=/admin/escola/jornadas/
escola/isto-nao-existe/  302 -> /entrar/google?next=/admin/escola/isto-nao-existe/
```

Um endereço inventado na hora dá exatamente a mesma resposta. Quem usar só isso
como prova de fora está provando que a célula está no ar e que a porta é
fail-closed — as duas coisas valem —, e **não** que a tela nova subiu.

**O que prova de verdade**, e são três coisas juntas:

1. O run de deploy verde, pelo veredito de `gh run view <id> --json status,conclusion`
   (nunca pelo exit de um pipe — ARMADILHAS §5.10).
2. Que aquele run CONTÉM o seu commit: `git merge-base --is-ancestor <seu> <o do run>`.
3. O 302 no endereço novo, lido pelo que ele de fato diz: a célula responde e o
   crachá vem antes. Escrever isso no relatório com essa ressalva é o que separa
   o relatório honesto do falso-verde.

Uma tela desta célula não tem prova de fora anônima melhor, e isso é DESENHO:
qualquer resposta que distinguisse rota existente de rota inventada entregaria o
mapa do bastidor a um estranho, que é justamente o que `porta.py::_nao_existe`
evita ao responder "não existe" em vez de "você não pode".

## Como achar os seus

O passo que denuncia é a **mutação deliberada, uma linha por vez**, e ela precisa
mutar a peça que o guarda diz proteger. Um roteiro que aplica a mutação, roda só
aquele teste e reverte antes da próxima custa poucos minutos e responde a única
pergunta que importa: *se eu quebrar isto de propósito, alguma coisa fica
vermelha?* Dos 16 guardas escritos naquele PR, 15 ficaram vermelhos na primeira
tentativa e 1 não; sem o roteiro, esse 1 teria entrado com nome bonito e valor
zero.

**A regra de bolso.** Antes de escrever a asserção, pergunte **onde mora o
mecanismo** desta promessa: no banco (constraint), na view (lista fechada,
fail-closed), na porta (contrato), ou no molde (o que se desenha). Meça ali.
Medir na superfície é o que produz o falso-verde mais caro deste projeto, porque
ele se parece exatamente com o verdadeiro.

**Parente.** É o padrão *falso-verde* e o *garantia sem mecanismo* da
`docs/decisoes/RETROSPECTIVA-FASE-D.md` encontrando-se num lugar novo: aqui o
mecanismo existe e está certo, e é o GUARDA que está no andar errado do prédio.
