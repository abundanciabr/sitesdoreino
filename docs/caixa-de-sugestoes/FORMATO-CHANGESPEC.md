# ChangeSpec — formato histórico v1

> Registro do desenho de agosto de 2026, sem autoridade para exigir aprovação,
> outra sessão, campos obrigatórios ou imutabilidade. Para trabalho atual,
> prevalece `AGENTS.md`: execute o pedido autorizado; peça a palavra do
> mantenedor apenas para gastar dinheiro real, apagar dados ou expor segredos.
> A trava de status da Caixa foi revogada em 06/09/2026 (§5).

Formato do documento que fica entre a decisão de produto e a implementação por agente. Complementa `ESPECIFICACAO-CELULA.md`.

## 1. Propósito e regra de autoria

O ChangeSpec traduz uma decisão de produto já tomada num corredor operacional que um agente de IA executa sem interpretar escopo livremente.

Na proposta original, outro agente ou sessão redigia o documento e o mantenedor
assinava `APROVADO_POR`. Essa separação deixou de ser condição para implementar
um pedido autorizado.

## 2. De onde nasce um ChangeSpec

```
Sugestao (linguagem do aluno)
    → decisão de produto (linguagem do produto)
    → ChangeSpec (linguagem da engenharia)
    → agente implementa
```

Quando o documento registrar uma sugestão da Caixa, o `suggestion_id` ajuda a
ligar a obra à origem. Trabalhos pedidos diretamente não dependem desse número.

**O caminho inteiro, com as estações que vêm antes e depois desta, está em
[`DA-IDEIA-A-OBRA.md`](DA-IDEIA-A-OBRA.md)** (01/09/2026). Sugestão grande passa
por um estudo de viabilidade no desenho original. Esse estudo pode registrar
premissas úteis, mas não condiciona o início de trabalho autorizado.

A decisão de produto — o passo do meio — agora tem um lugar concreto: `AvaliacaoInterna.decisao_produto`, na célula de sugestões. É onde a tradução de "problema do aluno" para "vamos resolver assim" fica registrada antes de virar ChangeSpec — uma linha, não um documento novo.

## 3. Campos do modelo histórico

- **CHANGE-ID** — `CS-{celula}-{sequencial}`, ex: `CS-PORTFOLIO-0001`
- **ORIGEM** — suggestion_id(s) da célula de sugestões
- **PROBLEMA** — reescrito em linguagem de produto; nunca a frase literal do aluno
- **EVIDÊNCIAS** — total de votos, autores únicos, comentários relevantes, puxados dos eventos da Célula de Sugestões
- **OBJETIVO** — o que muda para o aluno quando isso for entregue
- **FORA DO ESCOPO** — lista do que não seria construído nesta entrega, no modelo de 2026
- **CÉLULA(S) RESPONSÁVEL(IS)** — qual célula (ou células) este ChangeSpec autoriza a tocar
- **CONTRATOS PERMITIDOS** — contratos inter-célula que o agente pode chamar, por nome
- **CÉLULAS PROIBIDAS** — toda célula do sistema fora de CÉLULA RESPONSÁVEL, listada célula por célula, nunca resumida como "nenhuma outra"
- **CRITÉRIOS DE ACEITAÇÃO** — AC-01, AC-02... cada um verificável objetivamente, não uma sensação
- **TESTES OBRIGATÓRIOS** — nome dado aos testes previstos no modelo de 2026
- **RISCO E ROLLBACK** — como desfazer se algo sair errado em produção
- **DEFINITION OF DONE** — checklist final
- **APROVADO_POR** — nome e data; vazio até aprovação humana explícita

## 4. Critérios históricos, sem efeito de bloqueio

O modelo antigo considerava o ChangeSpec incompleto quando:

- `FORA DO ESCOPO` estiver vazio — se não dá para dizer o que fica de fora, não houve escopo de verdade
- `CÉLULAS PROIBIDAS` não listar cada célula do sistema fora de `CÉLULA RESPONSÁVEL`, uma por uma
- algum item de `CRITÉRIOS DE ACEITAÇÃO` não for verificável objetivamente — "melhorar a experiência" não é AC; "aluno publica portfólio e recebe URL pública em até 3 cliques" é
- `APROVADO_POR` estiver vazio

Esses critérios e a versão `-v2` eram convenções desse modelo. O documento pode
ser corrigido quando o escopo mudar; o histórico do Git guarda a versão anterior.

## 5. Gatilho no pipeline de status — REVOGADO em 06/09/2026

**A trava não existe mais, e esta seção fica aqui para dizer isso.** Até
06/09/2026 `Sugestao.status` só saía de `PLANEJADO` para `EM_DESENVOLVIMENTO`
com um ChangeSpec aprovado registrado, em três degraus (o ponto de
estrangulamento da moderação, o `Sugestao.save()` e um trigger no Postgres).

O mantenedor mandou tirar a trava, em pergunta estruturada, junto com a tela de
assinatura de obra do Admin, que era a única chave dela — remover só a tela
trancaria a fase para sempre. O motivo, medido na hora do pedido: nenhum
workflow, nenhum robô e nenhuma tarefa da fila leem `em_desenvolvimento`, então
a trava guardava um rótulo de roadmap, e não um gatilho de máquina. Quem
despacha robô nesta casa é a fila (`ci/fila.py`), que não conhece a Caixa.

O registro histórico de aprovações da Caixa permanece. Ele não condiciona a
execução de trabalho autorizado nem a mudança de status. O §4 acima também é
histórico.

O desenho anterior da aprovação está em
[`DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md`](DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md).
A célula não lê este documento em runtime; a existência de um registro não
confere o conteúdo do arquivo.

## 6. Exemplo preenchido

**CHANGE-ID:** `CS-PORTFOLIO-0001`

**ORIGEM:** suggestion_id 728 (canônica; mesclou 4 sugestões duplicadas sobre o mesmo problema)

**PROBLEMA:** alunos concluem projetos no curso mas não têm como reuni-los numa página pública que sirva para mostrar a clientes ou contratantes.

**EVIDÊNCIAS:** 218 votos, 176 autores únicos, 31 comentários

**OBJETIVO:** aluno consegue gerar uma URL pública com os projetos marcados como publicáveis no curso.

**FORA DO ESCOPO:**
- marketplace de venda de assets
- pagamento ou cobrança de qualquer tipo
- chat ou contato direto com visitante da página
- edição de layout além de um template fixo

**CÉLULA RESPONSÁVEL:** `portfolio` (nova célula)

**CONTRATOS PERMITIDOS:** `IdentityContract` (leitura de actor_id), `CourseEnrollmentContract` (leitura de projetos marcados como concluídos e publicáveis)

**CÉLULAS PROIBIDAS:** `checkout`, `payments`, `leads`, `sugestoes` (leitura direta — só via evento), `gamification`, `catalogo`

**CRITÉRIOS DE ACEITAÇÃO:**
- AC-01: aluno matriculado marca um projeto como publicável e gera URL pública em até 3 cliques
- AC-02: URL pública não expõe email, telefone ou qualquer dado além do marcado como público
- AC-03: aluno torna a página privada novamente a qualquer momento

**TESTES OBRIGATÓRIOS:**
- ator sem matrícula ativa não consegue publicar
- URL pública não vaza campos fora do whitelist
- despublicar remove o acesso público imediatamente

**RISCO E ROLLBACK:** feature flag por tenant; desativar oculta todas as URLs públicas sem apagar dado nenhum

**DEFINITION OF DONE:**
- [ ] AC-01, AC-02, AC-03 com teste automatizado
- [ ] nenhuma FK cruzando banco de célula
- [ ] feature flag testada em ambos os estados
- [ ] evento `sugestao.status-alterado` disparado ao mover suggestion_id 728 para `IMPLEMENTADO`

**APROVADO_POR:** _(vazio até revisão humana)_
