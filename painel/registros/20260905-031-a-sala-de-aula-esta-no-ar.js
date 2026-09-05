(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260905-031-a-sala-de-aula-esta-no-ar",
  tipo: "entrega",
  quando: "2026-09-05",
  titulo: "A sala de aula está no ar: meshcraft.top/cursos responde pela internet, de verdade",
  detalhe: "Conferido de fora, agora: https://meshcraft.top/cursos/healthz responde 200, e "
    + "https://meshcraft.top/cursos/ mostra o convite para entrar (é o comportamento certo para "
    + "quem ainda não fez login). É o fim do degrau 1.7 (PR #1069): o mapa das 34 portas, cada "
    + "aula com as 16 peças, o vídeo por link, as pausas e o quiz existem no site de verdade. Falta "
    + "o checkpoint (o envio da encomenda) para o aluno completar uma aula do começo ao fim, e o "
    + "editor no Admin ainda escreve o conteúdo (nenhuma aula está publicada, então o mapa aparece "
    + "vazio até você ou a professora publicarem a primeira).",
  autoridade: "sessao",
  evidencia: "curl -s -o /dev/null -w '%{http_code}' https://meshcraft.top/cursos/healthz -> 200; curl -s -L https://meshcraft.top/cursos/ -> tela 'Entrar no curso'",
  verificado_em: "2026-09-05",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
