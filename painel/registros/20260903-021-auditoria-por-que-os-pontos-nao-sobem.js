(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260903-021-auditoria-por-que-os-pontos-nao-sobem",
  tipo: "entrega",
  quando: "2026-09-03",
  titulo: "Auditoria: por que os pontos não sobem, e dois consertos reais encontrados",
  detalhe: "Você perguntou por que alunos que já criaram sugestões, votaram e usaram o fórum ainda não ganharam ponto nem subiram de nível. Investiguei o código de ponta a ponta (não o banco do servidor, que eu não acesso) e achei dois problemas reais, os dois já consertados neste PR:\n\n1. O XP de ações sociais (sugestão, voto, fórum) nasce em quarentena de 24h antes de aparecer no perfil do aluno, por desenho (para dar tempo de a moderação agir). O comando que libera essa quarentena nunca estava agendado para rodar sozinho - só existia para rodar à mão. Corrigido: agora ele roda automaticamente a cada minuto, junto com a outra tarefa que já roda assim.\n\n2. As 3 regras de pontuação do fórum (abrir tópico, responder, ter resposta aceita) já existiam desde 01/09, mas apareciam na sua tela de /admin/economia/ com o nome técnico cru, sem explicação em português - bem possível que você não as tenha reconhecido como 'regras do fórum' para ligar. Corrigido: agora aparecem traduzidas, como as outras.\n\nO que eu NÃO fiz: ligar regra nenhuma. Isso continua sendo decisão sua, na tela /admin/economia/ - e agora, com os dois consertos, ligar uma regra lá realmente vai fazer o ponto aparecer no perfil do aluno (depois da quarentena de 24h, quando ela existir).",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/918",
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
