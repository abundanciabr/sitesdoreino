---
schema_version: 2
armadilha: 286
estado: documentada
degrau: 5
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  motivo: `ci/tests/test_pecas_comuns_em_toda_celula_publica.py` varre TODAS as células públicas (lista MEDIDA de `painel/mapa-do-site.json`) e reprova nos dois sentidos: célula sem a peça e sem linha em `ci/pecas-comuns-em-falta.txt`, e linha declarada para peça que já existe. Ele roda no `muralhas` de todo PR. O guarda por célula (`services/gamificacao/tests/test_rodape.py::test_as_quatro_telas_vestem_a_mesma_moldura`) continua, e cobre o andar de baixo: a tela nova que nasce solta da moldura
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

   **Isto virou mecanismo no mesmo dia**, e a terceira metade era a que faltava:
   `ci/tests/test_pecas_comuns_em_toda_celula_publica.py` mais a lista
   `ci/pecas-comuns-em-falta.txt`. A catraca é a das outras dívidas da casa —
   buraco não declarado reprova, e declaração podre (linha para peça que já
   existe) reprova também. O segundo lado importa tanto quanto o primeiro: uma
   linha que mente sobre um buraco já consertado manda a próxima sessão gastar
   um dia procurando o que ninguém precisa achar.

   Uma célula "desenha a peça" quando tem o MOTOR **e** alguma tela dela usa o
   motor. Só a presença do arquivo não bastaria: uma célula pode tê-lo sem nunca
   chamar, e aí o guarda passaria verde sobre uma peça que ninguém vê.

**A pista falsa que custa a rodada:** o menu do topo tem tela de configuração
(`/admin/menu/`) com regra por página, e a versão vazia significa "esta página
não tem menu". É natural procurar a causa ali — *alguém desligou o menu das
Conquistas?* Não: a tela só oferece as células que estão em `CELULAS_COM_MENU`, e
uma célula sem motor não aparece ali nem para ser ligada. **Configuração ausente
e configuração desligada são o mesmo silêncio na tela, e caminhos opostos de
conserto.** O jeito rápido de separar os dois é perguntar ao disco:
`ls services/*/apps/core/menu.py`.

**O que a dívida declarada mostrava no dia em que ela nasceu**, e é um bom
retrato de por que ela precisa existir em vez de virar "conserta tudo agora":
sete linhas, e cada uma por um motivo DIFERENTE. A `checkout` está parada por
decisão do mantenedor; a `quiz` está de pé e sem nenhum quiz publicado (medido:
`/quiz/healthz` 200, `/quiz/quiz/crivo/` 404); a `sugestoes` tem rodapé PRÓPRIO,
e trocá-lo é decisão de tela dele, não conserto de robô; a `admin` serve
`/docs/` sem molde público compartilhado. Um guarda que exigisse tudo de uma vez
seria desligado na primeira semana, e um guarda desligado não é guarda.

**Origem:** 02/09/2026, pergunta do mantenedor depois de abrir
`/conquistas/`. A célula `gamificacao` foi ao ar em 01/09/2026 (registro
`20260901-013`), um dia depois de as duas peças nascerem nas outras células.
