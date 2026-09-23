# Execução de tarefas do projeto

A sessão que recebe o pedido executa dentro do mandato e responde pela
validação e entrega. Leia o Padrão de Trabalho em `CLAUDE.md`,
`CONSTITUICAO.md`, `RITOS.md` e as instruções dos caminhos envolvidos.

## Preparação e execução

1. Defina resultado, alvos, somente leitura, prova e fronteira do mandato.
   Priorize o caminho de compra e aprendizado. Separe dependências reais;
   trabalho paralelo exige alvos independentes e bancada própria.
2. Abra `python ci/sessao.py --celula <area> --tarefa <slug>`; sem serviço,
   use `--sem-container` e rode os testes dos alvos antes da primeira edição.
   O clone principal é somente leitura, conforme `RITOS.md` §1.
3. Consulte as armadilhas pertinentes. Declare modelo e esforço no brief por
   `python ci/economia_da_fabrica.py brief`. Fichas descrevem competências
   por tarefa, sem exclusividade por fornecedor. Subagente não cria outro
   nem pergunta ao mantenedor: devolve bloqueio à sessão responsável.
4. Preserve CODEOWNERS, contratos congelados, orçamento de arquivos e suítes
   de todas as células tocadas. Não acrescente trabalho fora do pedido.
   Falha de teste exige correção; ERROR exige diagnóstico do instrumento.
   Após duas correções sem sucesso, preserve os arquivos e commits e reporte
   o diagnóstico à sessão responsável, sem apagar trabalho.
5. Faça a revisão e o passe de remoção. Prove a mudança com comando e saída.
   Guardas novos exigem a prova de mutação de `ci/provar_guardas.py`.

## Entrega

Use `make pr`, conforme `painel/LEIA-ME.md`, com comandos de validação,
mensagem, corpo e detalhe. Ele embarca recibo e eventos; não repita esses efeitos.
Declare `Depende-de: #N` somente para dependência real, com número existente.
A integração segue `RITOS.md` §2; revisão adicional não é requisito de merge.
Validação local, integração e publicação exigem provas distintas.

A sessão continua responsável até o resultado terminal ou dívida registrada,
conforme a Lei 11. Bloqueio informa fato medido, impacto, responsável, ação
para destravar e prazo conhecido. Não devolva ao mantenedor um conserto técnico
que cabe no mandato. Antes de gesto exclusivo dele, leia `docs/guia-mantenedor.md`.

## Histórico encerrado

As seções e lições antigas estão na [revisão histórica](https://github.com/abundanciabr/sitesdoreino/blob/6bf9803a53f36a68cfe6365a45e250732710eeb0/RUNBOOK-LOTES.md).
Referências a elas apontam para aquela revisão. O protocolo anterior não rege
tarefas novas.
