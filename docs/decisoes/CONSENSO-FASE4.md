---
publico-para-ia: true
---
# Conselho da Fase 4: decidir por evidência

## Mandato

Cooperar para reduzir o tempo até uma entrega completa e verificada e seu
custo total. Não reduzir escopo, qualidade, segurança ou capacidade de recuperação.
A Fase 4 aqui é a medição dos pilotos da fábrica, definida em
[PROTOCOLO-FASE4-MEDICAO.md](PROTOCOLO-FASE4-MEDICAO.md).
Não é a fase homônima do painel de gestão, do curso ou do sininho.

Não existe garantia de ótimo global pelo acordo de IAs. A conclusão pode
identificar a melhor alternativa comparada no escopo medido; não pode prometer
o máximo de velocidade e o mínimo de dinheiro sem comparação e fonte.

## Uma discussão, várias contribuições

A página **Conselho da Fase 4**, em `/admin/documentos/conselho-fase4`, aponta
para a [discussão única no GitHub](https://github.com/abundanciabr/sitesdoreino/issues/1600).
Ela é a porta de entrada para o mantenedor.
Esta regra versionada é a referência técnica das IAs, também legível em
`/mapa-ia/planos/CONSENSO-FASE4.md` depois da publicação.

Use a issue para propostas, objeções e síntese. Tarefas, reservas e execução
continuam na fila e no balcão existentes; a discussão só aponta seus IDs.
Conclusões relevantes entram no livro pelo rito existente, sem outro placar.

Cada participante identifica sua sessão ou tarefa e escreve seu próprio
comentário. Correções são comentários novos com o link do anterior. Somente a
coordenadora edita a síntese do corpo da issue; ninguém edita parecer alheio.
Isso é disciplina: o GitHub permite editar comentários, e o editor do site
não protege contra duas gravações simultâneas. Não se promete bloqueio técnico.
A decisão final é preservada em documento versionado por PR.

Para entrar, leia o protocolo e a proposta em discussão; publique identificação,
especialidade e parecer. IAs com acesso ao repositório usam `gh issue view` e
`gh issue comment --body-file`; confirme o envio lendo o comentário retornado.
IAs somente leitoras entregam o parecer à coordenadora, que o transcreve com
autoria e origem. Não se concedem novas credenciais para participar.
Mesma conta GitHub não prova que dois pareceres são independentes.

## Duas rodadas e uma saída explícita

1. **Propostas independentes.** A coordenadora fixa revisão, escopo, critérios,
   participantes e prazo da rodada. Cada IA prepara a recomendação antes de ler
   as demais. Se já teve contato com elas, declara isso. Reuse auditorias atuais
   e atribua perguntas distintas; não repita a auditoria inteira por participante.
2. **Contraprova.** Cada IA examina a alternativa mais promissora e busca um
   requisito violado, uma evidência contrária ou um comando que a refute.
   A coordenadora publica a síntese identificada como uma nova revisão.

Cada rodada admite um parecer e uma réplica por participante, até 500 palavras
cada, com links para detalhes. Uma correção factual necessária não é proibida;
mudança que altere a conclusão exige nova revisão. Parecer longo não ganha peso.
Não mantenha modelos rodando para esperar: uma notificação por contribuição
ou um acompanhamento nativo solicitado substitui consultas repetidas.

Consenso significa que todos os participantes identificados confirmaram
explicitamente a mesma revisão da síntese. Silêncio, sessão parada e prazo
vencido não são concordância. Duas rodadas limitam o debate, não a coleta
necessária nem o escopo da Fase 4. Sem acordo, encerre a rodada como
**inconclusiva**, nomeie a objeção e leve o experimento discriminante à fila.
Só reabra com evidência nova ou correção que possa mudar a decisão.

## Parecer mínimo

Cada contribuição informa, em texto curto:

- Identidade da IA/sessão, pergunta recebida e contato prévio com outros pareceres.
- Proposta, alternativa atual e requisito completo que ambas precisam atender.
- Estado: hipótese, evidência observada ou benefício demonstrado no escopo.
- Revisão do código, protocolo e analisador, hash da entrada e revisão do instrumento.
- Comando executado, resultado, fonte autorizada e dados ausentes. Se não executou,
  escreva **NÃO RODEI**. Não publique telemetria privada, segredos ou dados pessoais.
- Tempo até resultado verificado, adoção, manutenção e retrabalho; chamadas,
  contexto e runner em suas unidades. Valor ausente permanece ausente.
- Risco, reversão, principal objeção e menor experimento capaz de mudar o parecer.

Um parecer incompleto volta ao autor com os campos ausentes e a ação de correção.
Fonte inacessível é evidência indisponível; dado incompatível não entra na comparação.
Erro do instrumento exige correção e nova medição, nunca aprovação por silêncio.

## Como escolher

Primeiro, descarte propostas que reduzam o resultado exigido ou violem um
requisito obrigatório. Compare apenas tarefas elegíveis e realmente comparáveis.
Custos de coordenação, revisão, falhas e retomadas pertencem ao custo observado.

Tempo e custo não viram uma nota arbitrária. Uma alternativa é dominada quando
outra é pelo menos tão boa nas duas dimensões e estritamente melhor em uma,
com evidência comparável e incerteza que sustente a conclusão. Estimativa
otimista não comprova dominância. Se uma opção ganha tempo e perde custo,
registre o trade-off e meça o que pode desempatar; não escolha por votação.

O protocolo vigente exige, conjuntamente, 20 tarefas elegíveis por condição,
10 pares válidos, revisão compatível, qualidade e segurança observadas sem
violação ou defeito escapado, redução da mediana com o limite superior de
97,5% da reamostragem abaixo de zero e redução do custo completo.
Ele é a fonte normativa; este conselho não pode afrouxá-lo ou inventar pares.

Custo completo em minutos inclui tarefa, adoção e manutenção. Chamadas,
contexto e runner ficam separados. Dinheiro exige preço efetivo e consumo
documentados; sem essa fonte, a conclusão não afirma economia monetária.
Não crie medição concorrente: use `ci/registrar_tarefa_fase4.py` e
`ci/analise_fase4.py` segundo o protocolo.

Se faltam dados, o conselho pode concordar sobre **o próximo experimento**,
sem declarar benefício ou liberar expansão. A Fase 3 mantém seus requisitos
de adoção, recuperação e auditoria independente antes da expansão.
Gasto real, ação irreversível ou mudança de contrato voltam ao mantenedor.

## Síntese que encerra a rodada

A coordenadora registra revisão, pergunta respondida, recomendação e motivo,
comparação com a alternativa atual, links das evidências, objeções e respostas,
concordâncias explícitas, ausências e limite da conclusão. O resultado é
**consenso sobre experimento**, **benefício demonstrado no escopo** ou
**inconclusivo**. Maioria não autoriza apagar uma objeção verificável.

Mudança de código, entrada, instrumento ou protocolo invalida a parte afetada
da conclusão. Preserve a versão anterior, recalcule e obtenha confirmação da
nova versão. A coordenação pode ser assumida por outra sessão mediante comentário
de passagem, com revisão e pendências identificadas, sem dois editores da síntese.
