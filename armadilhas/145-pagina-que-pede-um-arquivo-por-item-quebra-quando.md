# Página que pede UM arquivo por item quebra sozinha quando a lista cresce — e o erro acusa os dados, não a entrega

**Sintoma:** uma página que monta uma lista a partir de arquivos versionados
abre com a própria trava fail-closed acionada, e o número muda a cada vez:

```
⚠️ Este painel não pode ser lido.
O manifesto lista 86 registros, mas só 29 carregaram — algum arquivo de
registro sumiu ou está quebrado.
```

De manhã eram "58, só 2 carregaram". À tarde, "86, só 29". Quatro vezes num
dia. E o validador de linha de comando (`node painel/gerar_manifesto.js`) vem
**limpo** todas as vezes: nenhum arquivo quebrado, manifesto em dia, muralha
verde. Rodar os arquivos todos juntos num contexto compartilhado também dá
100% — o conteúdo está perfeito.

**Causa:** a página pedia **um arquivo por item** (aqui, um `<script>` por
registro, injetado com `document.write`). Abrir a página virava uma rajada de
86 pedidos HTTP simultâneos — e cada um deles atravessava a PORTA da área
administrativa, que pergunta à célula de identidade quem é a pessoa, com
**2 segundos de paciência** (`services/admin/apps/core/porta.py` +
`clients.py`). Sob a rajada, parte das perguntas estourava o tempo: a porta
respondia 503 (correto, fail-closed), o navegador recebia uma página de erro no
lugar do JS, aquele item não entrava na lista, e a trava da página gritava —
também correto.

Duas coisas tornam isso especialmente caro de achar:

1. **A mensagem acusa a fonte errada.** Ela diz "algum registro sumiu ou está
   quebrado", e o primeiro reflexo é auditar os dados. Os dados estavam
   íntegros o tempo todo; quem falhava era a ENTREGA. Uma sessão anterior
   fechou o caso como "não reproduzi" depois de validar os arquivos — que era
   exatamente o lugar onde não havia defeito.
2. **O defeito é proporcional ao sucesso do projeto.** O número de pedidos ERA
   o tamanho da lista. Cada tarefa registrada aumentava a chance de quebrar no
   dia seguinte, e nada no CI mede isso: em teste, cada pedido é sequencial e
   passa; em produção, chegam todos juntos.

**Solução:** o conteúdo vira **um arquivo só**, gerado — a página faz um pedido
em vez de N. O custo de abrir a página deixa de crescer com o tamanho dos
dados, e "carregou pela metade" deixa de ser um estado possível: ou o arquivo
chega, ou a falta é visível.

O que preservar ao empacotar, para não trocar um defeito por outro:

- **Mantenha a LISTA separada do CONTEÚDO** (`manifesto.js` com os nomes,
  `livro.js` com o conteúdo). É a comparação entre as duas contagens que
  detecta um pacote truncado. Um arquivo só não tem como detectar a própria
  falta.
- **Gere, nunca copie à mão**, e faça o `--conferir` do CI reprovar se o pacote
  divergir da fonte. Assim o empacotado não é uma segunda verdade — é derivado,
  como um índice.
- **Tire o BOM de cada fonte ao concatenar.** No começo de um arquivo o BOM é
  marca de codificação; no meio de um arquivo concatenado é caractere solto no
  código, e derruba o pacote INTEIRO em vez de uma entrada.
- **Deixe uma guarda que fixe a PROPRIEDADE, não a implementação:** "a página
  não faz um pedido por item" / "o número de pedidos não cresce com os dados"
  (`services/admin/tests/test_painel_vivo.py::test_o_livro_chega_em_UM_pedido_e_nao_um_por_registro`).

**A classe, para reconhecer da próxima vez:** *contagem que falha diferente a
cada tentativa não é dado corrompido — é concorrência ou tempo.* Dado corrompido
falha igual todas as vezes. Se o validador offline vem limpo e a tela vem
quebrada, o defeito está entre os dois: na entrega. (RETROSPECTIVA-FASE-D:
"prova de fora" — o único lugar onde este defeito existe é no navegador de
verdade, contra o servidor de verdade.)
