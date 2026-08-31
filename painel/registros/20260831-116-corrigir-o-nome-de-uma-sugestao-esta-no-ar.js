(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-116-corrigir-o-nome-de-uma-sugestao-esta-no-ar",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "Pode corrigir o 'turorial' agora: o botao esta no ar, e os dois deploys ficaram verdes",
  detalhe: "Os tres degraus subiram e o site ja tem a ferramenta que voce pediu hoje. Os dois deploys terminaram verdes, conferidos por mim no veredito real (nao no exit de um comando): a Caixa em 3min23s e a tela de administracao em 2min52s.\n\nCOMO USAR, em quatro passos:\n\n1. Abra meshcraft.top/admin/caixa/ (a Caixa de Sugestoes na sua area).\n2. Clique na sugestao do 'turorial'.\n3. Role ate a parte CORRIGIR O TEXTO, logo abaixo do que o aluno escreveu. Os campos ja vem preenchidos com o texto de agora.\n4. Conserte a letra e clique em salvar. Sao duas sugestoes com o mesmo erro, entao repita na outra.\n\nO aluno vai ver o nome certo, sem nenhuma marca de que alguem mexeu. O que estava escrito antes fica guardado logo abaixo do formulario, com a data e o seu nome, e so voce e quem administra enxerga isso.\n\nSE A TELA DISSER NAO, sao dois casos previstos: salvar sem ter mudado nada e recusado (em vez de dizer 'pronto' sem ter feito nada), e ideia ja apagada de vez nao mostra o formulario.",
  autoridade: "github",
  evidencia: "Os tres merges: https://github.com/abundanciabr/sitesdoreino/pull/779 (contrato, 8965b478), https://github.com/abundanciabr/sitesdoreino/pull/785 (a Caixa, 7c752edd) e https://github.com/abundanciabr/sitesdoreino/pull/788 (a tela, 9e5ae6be). DEPLOYS CONFERIDOS PELO VEREDITO REAL (gh run view --json status,conclusion, nunca por pipe): run 33445877252 (sha 7c752edd) status=completed conclusion=success em 3min23s; run 33446089185 (sha 9e5ae6be) status=completed conclusion=success em 2min52s. Prova de fora depois do deploy: https://meshcraft.top/admin/caixa/ responde 302 (manda para o login, que e o esperado numa area fail-closed) e https://meshcraft.top/forms/sugestoes/ responde 302. O que NAO foi verificado de fora: a correcao em si, que exige sessao de administrador — quem fecha essa ponta e o mantenedor, corrigindo a sugestao do 'turorial'.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
