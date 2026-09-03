(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260903-042-o-placar-novo-a-alunos-e-o-plano-estao-no-ar",
  tipo: "entrega",
  quando: "2026-09-03",
  titulo: "O placar novo, a data de 'virou aluno' e o plano reescrito estão no ar: os três deploys ficaram verdes",
  detalhe: "Veredito dos três deploys que os pousos de hoje à noite dispararam, "
    + "lido da fonte estruturada (gh run view --json), nunca de um exit de "
    + "comando:\n\n"
    + "1. A célula de alunos (PR #934, run 33816982339): success, na TERCEIRA "
    + "tentativa. As duas primeiras foram canceladas pela fila do servidor "
    + "(a esteira só guarda um deploy esperando por vez, e os pousos do placar "
    + "e do plano chegaram atrás dela); a vacina do deploy percebeu e "
    + "disparou de novo sozinha, sem ninguém pedir. A lista de alunos agora "
    + "devolve a data em que cada pessoa virou aluna.\n\n"
    + "2. A admin com o placar reformulado (PR #936, run 33817387581): "
    + "success. /admin/placar/ mostra a barra do mês e a meta de 500 até "
    + "15/12.\n\n"
    + "3. A admin com o plano reescrito (PR #937, run 33817600224): success. "
    + "O plano do painel de gestão está publicado em "
    + "meshcraft.top/mapa-ia/planos/.\n\n"
    + "Medido de fora, como um visitante: o placar sem sessão responde 302 "
    + "para o login (a porta está fechada, como deve); a porta de máquina da "
    + "alunos sem token responde 401 (existe e está trancada); a página dos "
    + "planos responde 200.\n\n"
    + "Nada mais depende de ninguém. O próximo degrau do plano (a restrição "
    + "desta semana) começa quando você quiser.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/actions/runs/33816982339 · https://github.com/abundanciabr/sitesdoreino/actions/runs/33817387581 · https://github.com/abundanciabr/sitesdoreino/actions/runs/33817600224",
  verificado_em: "2026-09-03",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "vender",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
