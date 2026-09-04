# 325 — O guarda que aponta para a peça errada passa por acidente, e a mutação é quem denuncia

**Sintoma.** Um teste-guarda está verde, o nome dele descreve exatamente a
promessa certa, a docstring explica bem por que a promessa importa, e ele **não
mede nada**. Nenhuma ferramenta acusa: cobertura conta a linha como coberta, a
suíte fica verde, e a revisão do PR lê o nome do teste e concorda com ele.

**Como apareceu aqui (04/09/2026, TAR-078, PR #1016).** A tela
`/admin/escola/jornadas/` mostra quem está dentro de uma sequência de mensagens.
A `mensageria` não guarda nome, e-mail nem telefone de ninguém (invariante 1 do
contrato congelado), e a tela tem de mostrar só o id opaco. O guarda escrito para
isso fazia o óbvio:

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

**A causa.** O guarda apontava para o MOLDE, e quem protege o dado não é o molde:
é a lista fechada de campos que a view monta antes de entregá-la ao template. O
que não entra naquele dicionário **não existe** para o molde, então nenhuma
mutação de template consegue vazar coisa nenhuma. O teste media um caminho que já
era impossível, e teria continuado verde para sempre — inclusive no dia em que
alguém trocasse a lista fechada por um `{**inscricao}` e abrisse o vazamento de
verdade, porque nesse dia o MOLDE continuaria sem pedir o campo.

**Solução.** Aponte o guarda para a peça que faz valer a promessa, e não para a
peça onde a promessa é visível:

```python
linha = _linha_de_inscricao({... "nome": "Maria de Tal", "email": "..."})
assert set(linha) == {"inscricao_id", "destinatario_id", "estado", ...}
```

Com isso, a mutação de UMA linha (`"motivo_de_saida": ...` virando `**inscricao,`)
ficou vermelha, como devia.

**Como achar os seus.** O passo que denuncia é a **mutação deliberada, uma linha
por vez**, e ela precisa mutar a peça que o guarda diz proteger. Um roteiro que
aplica a mutação, roda só aquele teste e reverte antes da próxima custa poucos
minutos e responde a única pergunta que importa: *se eu quebrar isto de
propósito, alguma coisa fica vermelha?* Dos 16 guardas escritos naquele PR, 15
ficaram vermelhos na primeira tentativa e 1 não; sem o roteiro, esse 1 teria
entrado com nome bonito e valor zero.

**A regra de bolso, para não repetir.** Antes de escrever a asserção, pergunte
**onde mora o mecanismo** desta promessa: no banco (constraint), na view
(whitelist, fail-closed), na porta (contrato), ou no molde (o que se desenha).
Meça ali. Medir na superfície é o que produz o falso-verde mais caro deste
projeto, porque ele se parece exatamente com o verdadeiro.

**Parente.** É o padrão *falso-verde* e o *garantia sem mecanismo* da
`docs/decisoes/RETROSPECTIVA-FASE-D.md` encontrando-se num lugar novo: aqui o
mecanismo existe e está certo, e é o GUARDA que está no andar errado do prédio.
