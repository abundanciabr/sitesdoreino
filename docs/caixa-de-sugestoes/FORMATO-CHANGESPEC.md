# ChangeSpec — Formato e Regras v1

Formato do documento que fica entre a decisão de produto e a implementação por agente. Complementa `ESPECIFICACAO-CELULA.md`.

## 1. Propósito e regra de autoria

O ChangeSpec traduz uma decisão de produto já tomada num corredor operacional que um agente de IA executa sem interpretar escopo livremente.

Regra não negociável: quem escreve e aprova o ChangeSpec não é o mesmo agente ou sessão que vai implementá-lo. Um agente pode ajudar a redigir o rascunho, mas a aprovação final é humana — registrada no campo `APROVADO_POR`. Se o mesmo agente que desenha o próprio escopo também o implementa, a propriedade de segurança que justifica esse documento desaparece: ele vira uma formalidade que o agente preenche para si mesmo.

## 2. De onde nasce um ChangeSpec

```
Sugestao (linguagem do aluno)
    → decisão de produto (linguagem do produto)
    → ChangeSpec (linguagem da engenharia)
    → agente implementa
```

Todo ChangeSpec referencia pelo menos um `suggestion_id` real da célula de sugestões. Se nasceu de várias sugestões mescladas, ou de um padrão identificado em várias sugestões (fase de clustering, mais adiante), referencia todas.

A decisão de produto — o passo do meio — agora tem um lugar concreto: `AvaliacaoInterna.decisao_produto`, na célula de sugestões. É onde a tradução de "problema do aluno" para "vamos resolver assim" fica registrada antes de virar ChangeSpec — uma linha, não um documento novo.

## 3. Campos obrigatórios

- **CHANGE-ID** — `CS-{celula}-{sequencial}`, ex: `CS-PORTFOLIO-0001`
- **ORIGEM** — suggestion_id(s) da célula de sugestões
- **PROBLEMA** — reescrito em linguagem de produto; nunca a frase literal do aluno
- **EVIDÊNCIAS** — total de votos, autores únicos, comentários relevantes, puxados dos eventos da Célula de Sugestões
- **OBJETIVO** — o que muda para o aluno quando isso for entregue
- **FORA DO ESCOPO** — lista explícita do que não será construído nesta entrega. Campo obrigatório, não pode ficar vazio
- **CÉLULA(S) RESPONSÁVEL(IS)** — qual célula (ou células) este ChangeSpec autoriza a tocar
- **CONTRATOS PERMITIDOS** — contratos inter-célula que o agente pode chamar, por nome
- **CÉLULAS PROIBIDAS** — toda célula do sistema fora de CÉLULA RESPONSÁVEL, listada célula por célula, nunca resumida como "nenhuma outra"
- **CRITÉRIOS DE ACEITAÇÃO** — AC-01, AC-02... cada um verificável objetivamente, não uma sensação
- **TESTES OBRIGATÓRIOS** — o que precisa ter teste automatizado antes do merge
- **RISCO E ROLLBACK** — como desfazer se algo sair errado em produção
- **DEFINITION OF DONE** — checklist final
- **APROVADO_POR** — nome e data; vazio até aprovação humana explícita

## 4. Regras de validade

Um ChangeSpec não está pronto para um agente pegar enquanto:

- `FORA DO ESCOPO` estiver vazio — se não dá para dizer o que fica de fora, não houve escopo de verdade
- `CÉLULAS PROIBIDAS` não listar cada célula do sistema fora de `CÉLULA RESPONSÁVEL`, uma por uma
- algum item de `CRITÉRIOS DE ACEITAÇÃO` não for verificável objetivamente — "melhorar a experiência" não é AC; "aluno publica portfólio e recebe URL pública em até 3 cliques" é
- `APROVADO_POR` estiver vazio

Imutabilidade: depois de aprovado, um ChangeSpec não é editado. Se o escopo mudar durante a implementação, nasce `CS-PORTFOLIO-0001-v2`, com um campo `SUBSTITUI` apontando para o anterior — o mesmo princípio do histórico append-only da célula de sugestões, aplicado aqui.

## 5. Gatilho no pipeline de status

`Sugestao.status` só sai de `PLANEJADO` para `EM_DESENVOLVIMENTO` se existir um ChangeSpec com `APROVADO_POR` preenchido referenciando aquele `suggestion_id`. Isso não é regra de interface — é validação no `save()` ou no serializer da célula de sugestões. Ninguém, agente ou pessoa apressada, move o status sem o corredor existir primeiro.

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
