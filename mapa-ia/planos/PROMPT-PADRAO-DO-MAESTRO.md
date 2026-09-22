# Prompt de execução de tarefa

O endereço foi preservado para links existentes. Cole o bloco abaixo em uma
sessão aberta no repositório e acrescente o pedido no fim.

```text
Execute o pedido abaixo no sitesdoreino. Leia CLAUDE.md, CONSTITUICAO.md,
RITOS.md e as instruções dos caminhos envolvidos antes de editar.

Comece pela experiência: quem usa, o que vê e faz, qual é a versão mais simples
que resolve o pedido inteiro e o que pode sair sem perda. Abra um checklist
com o resultado observável e a prova de cada etapa. Consulte arquivos e fontes
estruturadas para responder ao que o código já esclarece.

Abra bancada por python ci/sessao.py --celula <area> --tarefa <slug>;
sem serviço, acrescente --sem-container. Confira o baseline e as origens do
contexto direcionado. Trabalhe dentro dos alvos e do mandato do pedido.
Competências são por tarefa, sem atribuir papéis fixos a fornecedores.

Preserve as leis gerais, CODEOWNERS, contrato congelado e orçamento de arquivos.
Use a fila para trabalho fora do escopo e o livro para fatos. Se houver
subtarefas autorizadas, cada uma recebe alvos, somente-leitura, aceite e prova;
subagente não cria outro nem pergunta ao mantenedor. Bloqueio exige explicar
fato medido, impacto, responsável e ação que destrava.

Teste, revise e faça o passe de remoção. Publique pelo make pr conforme RITOS.md.
Integração é automática e publicação exige confirmação própria. Ao concluir uma
etapa, informe somente: Onde estou: passo N de M. Próximo passo: ação concreta.
Feche com checklist atualizado e O que mudou, O que foi verificado, Pendências,
Veredito e Instruções. Pendência deve dizer quem executa a próxima ação e se
ela começou; não anuncie trabalho sem executor iniciado.

PEDIDO:
```

## Mapa de execução obrigatório

Quando eu enviar uma tarefa, antes de qualquer comando, sub-agente, edição ou
brief, crie ou atualize fisicamente `mapa-ia/planos/ROADMAP-SESSAO.md` com um
mapa fechado e taxativo do início ao fim da tarefa. Depois mostre o conteúdo
essencial no chat. O arquivo é o contrato único do propósito e do checklist da
sessão, e continua vigente até o fecho. A fila, os PRs e a retomada continuam
sendo as fontes canônicas dos fatos externos e do estado entre sessões. O
roadmap deve conter:

```text
MAPA DA TAREFA: <resultado final em uma frase>
USUÁRIO E EXPERIÊNCIA: <quem usa, o que vê, faz e sente>
ESCOPO: <o que entra>
FORA DO ESCOPO: <o que não será feito>
DEFINIÇÃO DE PRONTO: <resultado observável e prova exigida>
RISCOS E DECISÕES DO MANTENEDOR: <somente o que realmente exige resposta>

## Plano
- [ ] 1. <etapa concreta> | dono: <IA> | prova: <comando, arquivo ou resposta>
- [ ] 2. <etapa concreta> | dono: <IA> | prova: <comando, arquivo ou resposta>
- [ ] 3. <etapa concreta> | dono: <IA> | prova: <comando, arquivo ou resposta>
Onde estou: passo 1 de 3
Próximo passo: <uma única ação>
```

Regras do mapa:

- A criação ou atualização de `ROADMAP-SESSAO.md` é a primeira ação obrigatória
  depois que a tarefa chegar. Não leia, meça, delegue, edite outro arquivo nem
  execute comando antes de registrar o mapa, salvo a resposta inicial exigida
  antes da tarefa.
- O resultado final vem antes das ações. Cada etapa deve ser necessária para
  esse resultado; se não for, corte-a.
- O mapa deve ter de 2 a 7 etapas. Uma só etapa é válida para tarefa trivial.
  Não crie etapas vagas como "continuar", "acompanhar", "analisar melhor" ou
  "fazer melhorias".
- Só existe uma etapa ativa por vez. Ao iniciar uma etapa, diga o passo e a
  prova esperada. Ao terminá-la, mostre a prova real, marque `[x]`, reimprima o
  checklist inteiro e indique a próxima etapa.
- `[ ]` significa pendente, `[>]` significa ativa, `[x]` significa concluída
  com prova e `[!]` significa bloqueada. Nunca marque `[x]` por intenção,
  relato de outra IA ou comando que não foi executado.
- Uma descoberta não muda o propósito. Se exigir novo alvo, novo resultado,
  nova decisão, nova etapa ou mais mandato, registre-a como desvio, explique o
  impacto e pare a parte afetada. Só o mantenedor autoriza mudança irreversível,
  cara, de lei, papéis, contrato ou escopo; o restante você decide em uma linha.
- Todo gesto deve apontar para uma etapa ativa e produzir uma mudança de estado,
  uma prova ou um bloqueio explícito. Se dois gestos consecutivos não produzirem
  nenhum dos três, pare, declare `NÃO AVANÇOU`, diagnostique a causa e escolha
  uma ação diferente ou devolva a decisão. Nunca repita o mesmo comando,
  sub-agente ou espera para simular avanço.
- O mapa não é substituído por uma lista nova no meio da sessão. Ao retomar,
  reconcilie-o com a retomada e preserve a identidade da tarefa. Se houver
  conflito, o mapa e o DoD originais vencem; a divergência vai para Pendências.
- Atualize `ROADMAP-SESSAO.md` com `[x]` somente depois da prova real de cada
  avanço. Releia o arquivo antes de cada etapa e grave nele o passo ativo, a
  última prova, os bloqueios e a próxima ação. Não invente passos nem mude o
  propósito sem registrar o desvio e obter a decisão exigida.
- Se houver bloqueio real que impeça a próxima etapa, marque `[!]`, registre o
  fato medido, o impacto, a ação que falta e o dono, e devolva a decisão ao
  mantenedor. Não contorne o bloqueio, não improvise escopo e não repita a
  espera.
