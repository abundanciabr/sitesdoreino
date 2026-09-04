---
schema_version: 2
armadilha: 304
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o plano chega de fora, em prosa, e nenhum portão lê prosa; o que existe é a tradução escrita na lei da célula (DECISAO §3) antes do primeiro PR, e os portões que recusam cada pedido já existem separadamente (contract_freeze para o contrato cedo, a catraca verde para o teste vermelho, o varredor do mapa para o consumo prometido)
sinal:
  - `congelado na Fase 0`
  - `constituição de célula fora do lugar`
  - `toca` apontando para caminho que não existe
  - `como esqueleto (falhando)`
  - `testes esqueleto (falhando)`
---

# Plano mestre escrito fora da casa pede o que o portão recusa: traduza a fase para a escada daqui ANTES de abrir o primeiro PR

**Sintoma.** O mantenedor traz um plano mestre inteiro, bem escrito, produzido
com IAs de fora (sem acesso a este repositório), e pede "quero implementá-lo no
site". A Fase 0 do plano lista, com todas as letras: *"contrato OpenAPI v1
congelado"*, *"testes-guarda como esqueleto (falhando)"*, *"esquema de eventos
v1"*, *"constituição da célula"*. Quem seguir a lista à risca abre três PRs que
os portões desta casa recusam ou que travam a célula no PR seguinte:

- **o contrato congelado antes da porta de máquina** deixa `make ci` da célula
  em ERROR até a porta existir (`armadilhas/228`; a gamificação pagou isso em
  30/08/2026), e o congelado escrito de cabeça nunca bate com o export
  (`armadilhas/243`);
- **o teste "esqueleto (falhando)"** é vermelho na `main`, e a catraca verde
  (RITOS.md §2) não admite; o esqueleto que "passa por enquanto" é falso-verde
  (retrospectiva, padrão 1), e o guarda dos guardas recusa `skip`;
- **o §8.3 do plano lista TODAS as rotas como contrato** (aluno, cliente,
  plantão, público, interno), quando aqui tela não é contrato: contrato é a
  porta de máquina, e cada rota a mais é uma rota a mais a defender pela borda
  (`armadilhas/103`, `186`).

**E os dois que mordem DEPOIS de você já ter traduzido os três de cima** (custaram
uma rodada de CI em 03/09/2026, run 33825263805, com as muralhas locais verdes):

- **a constituição da célula não pode existir antes da célula**:
  `ci/tests/test_constituicoes.py::test_toda_celula_tem_constituicao_e_nenhuma_e_orfa`
  reprova `constituicoes/AGENTS.<celula>.md` sem `services/<celula>/`, com a
  mensagem `constituição de célula fora do lugar` e a instrução de escrevê-la
  *a partir do código*. O plano pede "constituição" na Fase 0; aqui ela é
  rascunho em `docs/decisoes/` até a gênese;
- **as tarefas da escada que tocam a célula não podem nascer antes dela**:
  `ci/tests/test_conferencia_do_toca.py` reprova `toca: <celula>` para pasta
  inexistente, e a dispensa `cria` vale só para a gênese (dizer que seis
  tarefas "inauguram" a célula seria mentira no registro). Só as tarefas que
  NÃO tocam a célula (contrato, infra, docs) podem nascer antes; as outras, a
  gênese cria ao pousar. E esse guarda roda no `testador`, não nas `muralhas`:
  `ci/ci.py --apenas muralhas` verde localmente não o cobre.

E, por não conhecer as decisões anteriores do mantenedor, o plano assume o que
ele já decidiu ao contrário: **menores de idade** (a escola é 18+ desde
30/08/2026, reconfirmado em 03/09), **portfólio automático em `/@usuario`**
(a vitrine é o Estúdio, opt-in, decidida em 30/08 e 02/09), e **uma fase de
dinheiro** (diretiva de 22/08: pagamento por último). Caso real de 03/09/2026:
o plano da Fila do Primeiro Dólar (`PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md`)
tinha os seis pontos.

**Causa.** Um plano de fora descreve o **destino** e, por hábito de equipe
humana, o **rito de uma equipe humana** (congele o contrato cedo para os dois
times trabalharem em paralelo; escreva os testes vermelhos para a equipe ter
alvo). Ele não sabe que aqui: o congelado NASCE do export; PR não fica vermelho;
o mapa de células mede o consumo real e recusa promessa (`armadilhas/224`); e o
mantenedor já respondeu, no livro, perguntas que o plano ainda faz. A lista de
entregáveis do plano é uma lista de INTENÇÕES, e cada uma tem uma forma daqui.

**Solução: uma lei de tradução ANTES do primeiro PR, e o plano sem edição ao
lado.** O que funcionou em 03/09/2026:

1. **O plano entra no repositório sem uma vírgula mudada** (é o texto do dono;
   uma versão nova só nasce da resposta dele, nunca da mão do agente), com um
   cabeçalho dizendo que a lei vence onde divergirem.
2. **A `DECISAO-<assunto>.md` ganha uma seção "As emendas da casa"**, uma por
   ponto, cada uma citando o portão ou a decisão que a impõe e dizendo o que
   sai e o que fica. A régua da gamificação serve para todas: *guardar o que
   serve, remover o que só existia pelo pressuposto errado*.
3. **Cada entregável do plano vira a forma daqui:** contrato → anexo em papel
   agora, `contracts/` no degrau logo depois da porta de máquina; testes
   vermelhos → invariantes DECLARADOS na lei com o caminho do guarda, que
   entram no `INVARIANTES.md` no mesmo PR do guarda (precedente TAR-042);
   eventos → entram já (o manifesto não os amarra); rotas de tela → Parte B,
   fora do contrato; consumo previsto → `consome: []` na gênese; constituição
   → rascunho em `docs/decisoes/`, promovido na gênese.
4. **As divergências com decisões anteriores dele viram pergunta estruturada**,
   com a recomendação sendo a decisão que ele já tomou. Não se "conserta" o
   plano por conta própria nem se ignora o que ele já disse.
5. **O backlog do plano vira tarefas na fila** (`ci/fila.py criar` com
   `--depende-de`), não uma tabela que envelhece — mas só as que não tocam a
   célula nascem antes da gênese; as outras, o despacho da gênese cria ao
   pousar. Antes de abrir o PR, rode `python ci/ci.py --apenas testador` (ou
   ao menos `pytest ci/tests/test_conferencia_do_toca.py ci/tests/test_constituicoes.py`):
   as muralhas não cobrem esses dois.

**A leitura que evita a queda:** antes de abrir PR, leia o plano contra
`origin/main` **e contra o livro** (`painel/registros/`), procurando três
coisas: pedido que um portão recusa, pressuposto que ele já decidiu ao
contrário, e rito de equipe humana disfarçado de entregável. Vale para todo
plano que chegar de fora daqui em diante (a célula de cursos é o próximo).

**Origem.** Fase 0 da Fila do Primeiro Dólar, PR #946, 03/09/2026. Parente de
`armadilhas/148` (reconhecimento no espelho velho: projetar para um sistema que
não existe mais) e do padrão 8 da retrospectiva (viabilidade sem ler a
configuração), com a direção invertida: aqui quem não leu a configuração foi o
plano, e o agente é quem precisa ler por ele.
