# Prompt de execução do projeto

O nome deste arquivo permanece para preservar links existentes.
Cole o texto abaixo numa sessão com acesso ao repositório e acrescente a tarefa.

---

Execute o pedido no sitesdoreino dentro do mandato recebido. Leia `CLAUDE.md`,
`CONSTITUICAO.md`, `RITOS.md` e as instruções dos caminhos envolvidos.
As fichas descrevem competências por tarefa, sem papéis fixos por fornecedor.
Se ainda não houver tarefa, peça o resultado desejado antes de agir.
Para retomar trabalho, consulte a tarefa original e suas fontes de prova;
planos antigos não substituem as leis nem o estado medido.

## Mapa de execução obrigatório

Quando eu enviar uma tarefa, depois de abrir a bancada por `ci/sessao.py`, crie ou atualize fisicamente `mapa-ia/planos/ROADMAP-SESSAO.md` com um
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

- Registre `ROADMAP-SESSAO.md` na bancada, após as leituras e a abertura
  obrigatórias, antes de construir o resultado pedido.
- O resultado final vem antes das ações. Cada etapa deve ser necessária para
  esse resultado; se não for, corte-a.
- O mapa deve ter de 2 a 7 etapas. Uma só etapa é válida para tarefa trivial.
  Não crie etapas vagas como "continuar", "acompanhar", "analisar melhor" ou
  "fazer melhorias".
- Só existe uma etapa ativa por vez. Ao iniciar uma etapa, diga o passo e a
  prova esperada. Ao terminá-la, registre a prova real, marque `[x]` no arquivo e informe somente
  "Onde estou: passo N de M. Próximo passo: ..." no chat.
- `[ ]` significa pendente, `[>]` significa ativa, `[x]` significa concluída
  com prova e `[!]` significa bloqueada. Nunca marque `[x]` por intenção,
  relato de outra IA ou comando que não foi executado.
- Uma descoberta não muda o propósito. Se exigir novo alvo, novo resultado,
  nova decisão, nova etapa ou mais mandato, registre-a como desvio, explique o
  impacto e pare a parte afetada. Só o mantenedor autoriza mudança irreversível,
  cara, de lei, contrato ou escopo; o restante você decide em uma linha.
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

### Conferência do propósito

Toda execução ou revisão deve conferir as etapas do mapa, os alvos e a prova
exigida. Desvio é relatado com etapa afetada, fato medido, impacto e próximo
passo permitido. A sessão responsável atualiza o mapa sem ampliar o mandato.
Uma revisão mede a entrega contra o pedido; ela não cria autoridade adicional.

## Como executar e entregar

- Abra bancada própria com `python ci/sessao.py --celula <area> --tarefa <slug>`;
  sem serviço, acrescente `--sem-container` e rode os testes dos alvos.
- Defina brief fechado quando houver delegação: célula, alvos, somente leitura,
  fora de escopo, prova, mandato, modelo e esforço por
  `python ci/economia_da_fabrica.py brief`. Delegação não exige uma marca de IA.
- Meça antes de afirmar. Consulte Git, GitHub, fila e livro conforme a tarefa;
  ausência de medição deve aparecer como NÃO MEDIDO. Leia somente o contexto
  pertinente, com `rg` e trechos dos arquivos grandes.
- Decida o que cabe no mandato. Dinheiro, segredo, contrato e ação irreversível
  exigem a decisão exclusiva do mantenedor, conforme a regra 4 de `CLAUDE.md`.
  Subagente devolve bloqueio à sessão responsável, sem perguntar diretamente.
- Revise, valide e publique por `make pr`, com registro e eventos a bordo.
  A integração segue `RITOS.md` §2, sem atestado ou etiqueta de pouso.
  Não consulte checks em laço. Prove separadamente validação, integração e
  publicação e responda pela entrega até o resultado terminal ou dívida registrada.
- Publique `## Plano` com caixinhas uma vez na abertura. Durante a execução,
  informe "Onde estou: passo N de M. Próximo passo: ..." ao concluir uma etapa.
  Atualize o mapa físico com a prova; não repita o checklist no chat.
- No fecho, checklist final e os blocos O que mudou, O que foi verificado,
  Pendências, Veredito e Instruções. Português, sem travessão e sem elogio.
  Se faltar entrega, descreva fato, responsável, ação para destravar e prazo.
