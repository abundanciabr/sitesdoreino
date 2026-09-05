---
schema_version: 2
armadilha: 346
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o portao de linter/CI nao tem como distinguir "mudar de estado corretamente sem tocar em progresso.py" de "esquecer de mudar o estado"; o que prova isto e o proprio teste de integracao do reenvio (test_laudo.py::test_devolvido_muda_o_envio_a_porta_e_permite_reenvio), que so existe porque a sessao releu o modelo antes de escrever o servico
sinal:
  - "EnvioRecusado: Seu envio já está na fila de revisão"
  - "checkpoint.entregar recusa o reenvio mesmo depois do laudo devolvido"
---

# Devolver a porta não é concluir a porta, e não mora em `progresso.py`

**Sintoma (que este despacho NUNCA deixou acontecer, porque foi pego antes de
escrever o teste):** um laudo `devolvido` grava `Envio.estado = "devolvido"` e
emite `checkpoint.devolvido.v1` corretamente — e mesmo assim o aluno tenta
reenviar e recebe `EnvioRecusado: Seu envio já está na fila de revisão.
Espere o laudo antes de entregar de novo`, apesar de o laudo JÁ TER CHEGADO.

**Causa.** `envio.py::entregar` só aceita entrega quando
`Progresso.estado` está em `{em_producao, devolvida}`
(`ESTADOS_QUE_ENTREGAM`). Gravar o `Envio.estado` como `devolvido` não muda o
`Progresso` — são duas tabelas diferentes, e nada as sincroniza sozinho.
Enquanto ninguém escrever `Progresso.estado = DEVOLVIDA`, a porta continua
`enviada` para sempre, e o aluno fica sem caminho de volta mesmo com o laudo
já emitido.

**A tentação, e por que ela é um beco sem saída nesta célula.** A resposta
óbvia é "então acrescento uma função `devolver(progresso, *, laudo)` em
`apps/cursos/progresso.py`, do lado de `concluir`". Mas o despacho da tarefa
declarou esse arquivo **SOMENTE-LEITURA** ("consuma `concluir`, não mude") —
e com razão: `progresso.py` é o dono do invariante [INV-CUR-P2]
(`tests/test_inv_p2_a_porta_so_abre_por_laudo.py`), com um guarda que mede a
ASSINATURA de `concluir` por `inspect` e conta quantas vezes
`Progresso.Estado.CONCLUIDA` é atribuído no arquivo inteiro (exatamente uma).
Acrescentar uma segunda função ali — mesmo sem tocar em `concluir` — muda o
arquivo que o despacho marcou como intocável, e arrisca reabrir a discussão
de "quantos caminhos gravam `Progresso.estado`" que aquele guarda existe para
fechar.

**Solução: a transição de "devolvido" mora no MESMO arquivo que decide a
decisão — `apps/cursos/laudo.py` — e mexe no modelo direto, sem passar por
`progresso.py`.**

```python
# apps/cursos/laudo.py, dentro do `with transaction.atomic():` de `emitir()`
if decisao in portas.DECISOES_QUE_ABREM:
    portas.concluir(progresso, laudo=laudo)          # o ÚNICO dono de CONCLUIDA
    eventos.emitir_aula_concluida(...)
else:  # devolvido
    progresso.estado = Progresso.Estado.DEVOLVIDA     # NÃO é concluir(); é outro campo
    progresso.data_de_retorno = laudo.data_de_retorno
    progresso.save(update_fields=["estado", "data_de_retorno"])
    eventos.emitir_checkpoint_devolvido(laudo)
```

Isto **não** enfraquece o [INV-CUR-P2]: o invariante protege especificamente
`Progresso.Estado.CONCLUIDA` (o guarda dele conta atribuições desse valor
exato, só em `progresso.py`), e devolver grava `DEVOLVIDA`, um valor
diferente, por um caminho diferente. `progresso.py` continua sendo o único
lugar que grava `concluida`; ele nunca prometeu ser o único lugar que grava
`devolvida` — essa promessa não está em invariante nenhum, porque devolver
não é uma regra da PORTA (que aula abre): é uma regra do LAUDO (o que a
decisão faz depois de aceita).

**O que confirma que a régua certa é "quem decide, quem grava", não "todo
`Progresso.estado` mora num arquivo só":** o campo `Progresso.data_de_retorno`
já existia no modelo desde o degrau 1.8 (TAR-154), com o comentário "(se
devolvida)" — o modelo **já previa** este caminho antes de o laudo (degrau
2.2) nascer. Reconhecer isso na hora de desenhar o serviço é o que evita
escrever uma segunda tabela ou um campo novo para o mesmo fato.

**Como perceber isto ANTES de escrever o teste, e não depois de um vermelho:**
ao integrar um serviço novo com um modelo de estado existente, pergunte "que
ESTADOS este serviço faz o modelo atravessar?" para CADA ramo de decisão, não
só o ramo óbvio (aqui, `concluir` já estava pronto e chamava a atenção; o
ramo `devolvido` parecia "só mudar o `Envio`" porque o evento e o
`Envio.estado` já cobriam a metade visível do trabalho).

**Origem.** Degrau 2.2 da célula `cursos` (TAR-156, 05/09/2026), ao escrever
`apps/cursos/laudo.py::emitir` e notar, relendo `envio.py::ESTADOS_QUE_ENTREGAM`,
que nada preparava o reenvio depois de um laudo devolvido.
