# Os quatro pareceres — insumo histórico, NÃO lei

Estes quatro arquivos (`recomendação-*.txt`) são as respostas de quatro IAs
externas à consulta de i18n feita pelo mantenedor em **23/08/2026**. O prompt
que as gerou está em `PROMPT-CONSULTA-OUTRAS-IAS.md`.

## Leia isto antes de citar qualquer coisa deles

**A lei deste projeto é o `PLANO-I18N.md`** (decisões D1–D9) e a **Receita R12**
do `CAMINHO-DOURADO.md`. Os pareceres são a matéria-prima que os produziu —
valiosos como registro de *por que* cada decisão foi tomada, e perigosos se
lidos como instrução.

**Eles contêm erros técnicos verificados**, catalogados um a um no **§6 do
`PLANO-I18N.md`**. O mais grave, para quem for mexer em roteamento: um dos
pareceres usa **sintaxe de rota do Traefik v2** (`/{lang:[a-z]{2,3}}/...`), que
foi **removida no v3** — e este repositório roda Traefik v3.4. Copiada ao pé da
letra, ela derruba o deploy. Há também: um middleware de header dinâmico que o
Traefik de fábrica não faz, uma regex sem fronteira de segmento, afirmações
erradas sobre o PyYAML e sobre binários do gettext, e conselhos de SEO acima do
que a documentação do Google sustenta.

**Não edite estes arquivos.** São registro do que foi respondido, não documento
vivo. Correção de conteúdo vai no §6 do plano, que é onde a auditoria mora.

## Por que estão versionados

Porque o §6 do plano os cita pelo nome, e **agente trabalha dentro de um
`git worktree`, que só contém arquivo rastreado** — enquanto viveram apenas no
disco do mantenedor, a citação apontava para um caminho que nenhum agente
conseguia abrir.

## O que a consulta ensinou sobre consultas

Do §6 do plano, vale repetir aqui: convergência entre LLMs mede
**convencionalidade, não correção** — os quatro concordaram entre si em pontos
que só a verificação contra o repositório confirmou ou derrubou. O valor real
veio de medir (rodar o PyYAML, checar a versão do Traefik, ler o código), não
de contar votos. **Se o rito for repetido: menos pareceres, dobro de
verificação.**
