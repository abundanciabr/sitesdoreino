---
schema_version: 2
armadilha: 286
estado: documentada
degrau: 5
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  motivo: o guarda desta entrada é `services/gamificacao/tests/test_rodape.py::test_as_quatro_telas_vestem_a_mesma_moldura`, e ele só protege a célula em que mora. O guarda que faltava — o que varre TODAS as células públicas e pergunta se cada uma desenha as peças comuns — não existe no repositório, e é isso que fez esta queda ser invisível por dois dias
---

# Célula pública nova nasce SEM a peça que todas as outras já têm, e nenhum portão pergunta

**Sintoma.** Uma área do site abre normalmente, com o conteúdo certo, e sem o
menu do topo e sem o rodapé que todas as outras páginas têm. Nenhum teste fica
vermelho, nenhuma muralha reclama, o deploy passa verde. Quem descobre é o dono
do site abrindo a página com os próprios olhos, e a pergunta que ele faz é
exatamente a certa: *"como podemos configurar para que em todas as páginas tenha
o menu e o rodapé?"*

Medido em 02/09/2026 em `https://meshcraft.top/conquistas/`: `<footer` zero
ocorrências, `barra-do-site` zero ocorrências, num dia em que `/`, `/cadastro` e
`/forum/` traziam as duas peças.

**Causa.** A peça comum nasceu DEPOIS da célula, e a cobertura dela foi definida
por onde havia molde compartilhado, não por onde havia página. O rodapé do site
nasceu na `funil` em 31/08/2026 e chegou ao `forum` no mesmo dia; as duas têm um
template-base que toda tela estende, então bastou desenhar uma vez. A
`gamificacao` tinha quatro telas e NENHUMA moldura — quatro documentos HTML
completos, cada um com o próprio `<head>` e o próprio fim de página. Não havia
onde pôr a peça de uma vez, então ela não foi posta.

Isto é a `armadilhas/242` um andar acima. Ela ensina que `{% include %}` por
template faz a peça sumir da primeira TELA nova; aqui a peça sumiu da primeira
CÉLULA nova, pelo mesmo defeito de raiz: *"em todas as páginas" dependia de
alguém lembrar*. E a diferença de andar importa, porque a cura dela (processador
de contexto + varredura do urlconf) é **por célula**: os dois guardas do `forum`
estavam verdes e corretos no dia em que `/conquistas/` estava sem rodapé, porque
nenhum deles sabe que a `gamificacao` existe.

É também a Classe 8 do `PLANO-MESTRE-ROBOS-SEM-COLISAO.md` (mapa mantido à mão
envelhece em silêncio) com o mapa implícito: a lista de "quem desenha as peças
comuns" nunca foi escrita em lugar nenhum, então não teve como ficar
desatualizada — ela já nasceu incompleta.

**Solução, em três metades, e a terceira é a que faltava:**

1. **A célula ganha uma MOLDURA de verdade** (`templates/<celula>/moldura.html`),
   e toda tela dela a estende. Sem essa casa, as duas metades seguintes não têm
   onde morar. Quando o nome `base.html` já for de uma TELA, não renomeie a tela:
   chame a moldura de `moldura.html` e siga.
2. **Quem decide é processador de contexto; quem desenha é a moldura**, com a
   varredura do urlconf real como guarda (o molde inteiro está na
   `armadilhas/242`). Acrescente um guarda a mais, que a 242 não tem: **a
   varredura da PASTA de templates**, provando que nenhuma tela ficou solta.
3. **Ao levar uma peça comum para o site, a pergunta não é "quais células têm
   molde?" — é "quais células servem página a gente?"**. A lista se mede, não se
   escreve: `painel/mapa-do-site.json`, filtrado por `alcance: publico` e
   `para_quem` em `visitante`/`aluno`, responde isso sem envelhecer. Célula
   pública que não desenha a peça é dívida declarada, e precisa de linha escrita
   dizendo por quê.

**A pista falsa que custa a rodada:** o menu do topo tem tela de configuração
(`/admin/menu/`) com regra por página, e a versão vazia significa "esta página
não tem menu". É natural procurar a causa ali — *alguém desligou o menu das
Conquistas?* Não: a tela só oferece as células que estão em `CELULAS_COM_MENU`, e
uma célula sem motor não aparece ali nem para ser ligada. **Configuração ausente
e configuração desligada são o mesmo silêncio na tela, e caminhos opostos de
conserto.** O jeito rápido de separar os dois é perguntar ao disco:
`ls services/*/apps/core/menu.py`.

**Origem:** 02/09/2026, pergunta do mantenedor depois de abrir
`/conquistas/`. A célula `gamificacao` foi ao ar em 01/09/2026 (registro
`20260901-013`), um dia depois de as duas peças nascerem nas outras células.
