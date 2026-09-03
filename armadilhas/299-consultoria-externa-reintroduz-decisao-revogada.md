# 299 — Documento de consultoria externa reintroduz uma decisão que o mantenedor já revogou, e volta a cada versão

**Sintoma.** O mantenedor traz um documento de estratégia escrito por uma IA de
fora (arquitetura de receita, plano de produto, blueprint) e pede para
transformá-lo em plano da casa. O documento é longo, bem escrito e assume um
fato que o projeto já decidiu ao contrário. No caso real de 03/09/2026: três
versões da "Arquitetura de Receita Meshcraft 10X" (v1, v2 e v3), e as três
assumem alunos menores de 18 (pai ou mãe como pagador, "proteção de menores",
campo `guardian` no modelo de dados), quando a decisão do mantenedor de
30/08/2026 é que a escola é 18+ e nunca terá menores (`DECISAO-gamificacao.md`
§9, PR #677). A v2 e a v3 foram escritas DEPOIS de a v1 ter sido corrigida em
conversa: a IA de fora não vê a correção, e cada versão nova traz o fato de
volta.

Nenhum erro aparece. O plano derivado sairia completo, coerente com o
documento de origem, e errado em relação à casa.

**Causa.** A IA externa não lê `docs/decisoes/` nem a memória do projeto; ela
lê o que o mantenedor colou na conversa dela. Toda premissa que não foi
colada continua valendo lá, e volta em cada versão. E o agente daqui, ao ler
um documento de 190 itens, tende a avaliar a arquitetura pela consistência
INTERNA dela (ela é consistente) em vez de confrontar cada premissa com as
decisões da casa.

É a mesma família do padrão 8 da `RETROSPECTIVA-FASE-D.md` (não afirme
viabilidade sem ler a configuração): aqui a "configuração" são as decisões do
mantenedor, e o documento externo é a prosa que as ignora.

**Solução.** Antes de transformar documento externo em plano:

1. **Liste as premissas de fato** do documento (quem é o cliente, quem paga,
   que ferramentas existem, que equipe existe, que produto vende) e confronte
   cada uma com `docs/decisoes/DECISAO-*.md` e com a memória da sessão. No
   caso real, além dos menores, o documento assumia setter/closer/SDR (não
   existem), um CRM contratado (decidido em 03/09: a plataforma é o CRM) e
   checkout ativo (congelado desde 22/08).
2. **Toda divergência volta ao mantenedor em pergunta estruturada**, uma vez,
   consolidada, com a decisão anterior citada e a opção "manter a decisão"
   marcada como recomendada. Não revogue sozinho e não acate sozinho.
3. **Registre a reconfirmação** (memória da sessão e, se for fato do
   projeto, registro no livro), porque a versão seguinte do documento externo
   vai trazer a premissa de volta, e a pergunta não deve ser feita duas vezes.
4. **No plano derivado, escreva a tabela "decisões do mantenedor que este
   plano executa"** no topo, com data, antes de qualquer conteúdo do documento
   externo. Quem ler o plano sem ter lido a conversa enxerga a fronteira.

**Onde vive o caso:** `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` §1 (a tabela
de decisões) e a memória `project_alunos_todos_maiores_de_18`.
