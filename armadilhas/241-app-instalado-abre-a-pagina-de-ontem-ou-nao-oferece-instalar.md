---
schema_version: 2
armadilha: 241
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: services/funil/tests/test_instalar_o_app.py
sinal:
  - `o app instalado mostra a p.gina de ontem`
  - `The service worker navigation scope`
  - `Site cannot be installed: (no matching )?service worker detected`
---

# O site instalado no celular abre a página de ontem, ou o navegador nunca oferece instalar

**Sintoma**, em qualquer uma das duas metades:

1. o navegador não oferece a instalação, e o convite da tela nunca aparece,
   ainda que o `manifest.webmanifest` responda 200 e esteja no `<head>`;
2. o app instalado abre uma versão VELHA do site. A pessoa jura que a página
   mudou, o site aberto no navegador mostra a versão nova, e o ícone da tela de
   início mostra a de ontem.

**Causa:** as duas saem do mesmo pedaço, o *service worker*, e de duas regras
dele que não se parecem com nada do resto da plataforma.

**A primeira regra: um service worker só manda na pasta de onde foi baixado.**
Servido de `/static/funil/sw.js`, o escopo dele é `/static/` — ele não vê
navegação nenhuma do site, o navegador conclui que o site não funciona sem
rede, e a instalação não é oferecida. Não há erro em log nenhum: o arquivo
responde 200, o registro dá certo, e o que falha é a única coisa que
interessava. Por isso ele tem rota PRÓPRIA na raiz (`/sw.js`, em
`services/funil/config/urls.py`) em vez de ser mais um arquivo de `/static/`.

**A segunda regra: quem responde a navegação passa a ser o service worker, e
não o servidor.** Um `fetch` que olha o cache primeiro entrega a página que ele
guardou, e o servidor pode ter sido atualizado dez vezes desde então. Nesse
estado, deploy verde e site velho convivem sem nenhuma contradição visível: o
site aberto no navegador comum vem do servidor e está certo; só quem instalou
vê a página velha. É falso-verde de um jeito novo, porque a medição de fora
(`curl`, o run do deploy) mede o servidor, e o defeito não está lá.

**Solução — três coisas, e nenhuma delas é opcional:**

1. **Sirva o service worker da RAIZ** (rota própria), nunca de dentro de
   `/static/`. Se um dia ele precisar sair de outro lugar, o cabeçalho
   `Service-Worker-Allowed: /` é o que amplia o escopo, e ele já vai na
   resposta da view.
2. **Rede primeiro, cache depois, sempre.** O cache é rede de segurança para
   abrir sem conexão, nunca fonte de verdade. Em `services/funil/static/funil/sw.js`
   isso é literalmente a ordem do código, e
   `test_o_service_worker_pede_a_rede_antes_do_cache` mede a ordem no arquivo:
   invertê-la reprova.
3. **`Cache-Control: no-cache` na resposta do próprio `/sw.js`.** Sem isso o
   navegador pode segurar o service worker por até 24 horas, e a correção que
   você acabou de mergear não alcança quem já instalou. É o único arquivo do
   site em que um cache de um dia significa um dia de site errado para quem
   mais usa.

**A parte que nenhum teste pega, e por isso está escrita aqui:** quem já
instalou o app carrega uma cópia do service worker antigo no aparelho dele. Uma
mudança no `sw.js` só chega àquela pessoa no carregamento seguinte, e o
`skipWaiting()` está lá justamente para não esperar todas as abas fecharem.
Nenhuma medição feita daqui prova o que está rodando no celular de outra
pessoa: se um relato de "está velho" chegar, a primeira pergunta é há quanto
tempo aquele aparelho abriu o app, e não o que o servidor responde.

**Contexto:** nasceu em 31/08/2026 com o PWA da célula `funil` (o mantenedor
pediu o site instalável para poder mandar aviso a quem usa iPhone). Não custou
uma queda: as três regras entraram já com guarda, e esta entrada existe para
que a primeira queda seja em outro projeto, não neste.
