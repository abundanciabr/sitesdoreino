# Prompt rápido de execução do projeto

O nome deste arquivo permanece para preservar links existentes.
Cole o texto abaixo numa sessão com acesso ao repositório e acrescente a tarefa.
Para um mapa físico detalhado, use `PROMPT-PADRAO-DO-MAESTRO.md`.

---

Execute a tarefa no sitesdoreino dentro do mandato recebido. Leia `CLAUDE.md`,
`CONSTITUICAO.md`, `RITOS.md` e as instruções dos alvos. As fichas descrevem
competências por tarefa, sem papéis fixos por fornecedor.
Se ainda não houver tarefa, peça o resultado desejado antes de agir.

- Publique `## Plano` com caixinhas uma vez na abertura. Defina o resultado,
  os alvos, o que é somente leitura e a prova que encerra o pedido.
- Abra bancada com `python ci/sessao.py --celula <area> --tarefa <slug>`.
  Sem serviço, use `--sem-container` e rode os testes dos alvos antes de editar.
- Carregue só contexto pertinente. Meça nas fontes da tarefa antes de afirmar;
  use `rg` e trechos dos arquivos grandes. Escreva NÃO MEDIDO quando faltar prova.
- Execute o que cabe no mandato. Subagente devolve bloqueio à sessão responsável;
  decisões exclusivas do mantenedor seguem a regra 4 de `CLAUDE.md`.
- Revise, faça o passe de remoção e publique por `make pr`, com validação,
  recibo e eventos. Integração automática segue `RITOS.md` §2. Não consulte
  checks em laço. Validação, integração e publicação exigem provas distintas.
- Ao concluir etapa, informe "Onde estou: passo N de M. Próximo passo: ...".
  No fecho, checklist final e O que mudou, O que foi verificado, Pendências,
  Veredito e Instruções. Se faltar entrega, diga fato, responsável, ação para
  destravar e prazo. Português, sem travessão e sem elogio.
