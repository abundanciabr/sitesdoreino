(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-052-o-deploy-do-ao-vivo-falhou-e-a-maquina-se-curou-sozinha",
  tipo: "incidente",
  quando: "2026-09-02",
  titulo: "A publicacao do ao vivo falhou, a maquina se curou sozinha, e esta tudo no ar",
  detalhe: "Registro do que aconteceu DEPOIS que o rascunho ao vivo entrou. Conto porque foi um susto de verdade, e porque o final e a melhor noticia do dia.\n\nO QUE FALHOU: na hora de publicar, a porta de entrada da VPS engasgou. O sistema tentou tres vezes, com pausa entre elas, e as tres foram recusadas. Nao foi o codigo: ele tinha passado em todos os testes. E o soluco conhecido da maquina, o que mais sangrou tempo nesta casa.\n\nO QUE ACONTECEU SEM NINGUEM PEDIR, e e por isso que vale registrar: primeiro, a reversao automatica devolveu a parte afetada para a versao anterior, entao o site nunca ficou fora do ar. Depois, a vacina do deploy ACORDOU SOZINHA, mediu a porta, viu que ja estava respondendo, e redisparou a publicacao. Dessa vez passou.\n\nEU NAO PRECISEI TENTAR NADA A CEGAS, e voce nao precisou fazer nada. As duas pecas que trataram disso foram construidas aqui em agosto, exatamente para este caso, e hoje elas trabalharam sem plateia.\n\nO QUE FICOU NO AR: o rascunho ao vivo, mais as tres coisas do pacote anterior (resposta curta, mais rapida, e a pagina levando voce ate o texto). Conferido de fora, no site de verdade.",
  autoridade: "github",
  evidencia: "Run 33687662127: primeira passada com deploy (admin) failure apos 3 tentativas, reversao automatica success, deploy (forum) cancelled. Vacina 33688428913 completed/success, que redisparou o run. Segunda passada: deploy (admin) success, deploy (forum) success, RUN completed/success. Conferido de fora: meshcraft.top/forum HTTP 200 e meshcraft.top/forum/static/forum.js HTTP 200 com 5428 bytes e text/javascript. Vereditos lidos de gh run view --json, nunca de pipe.",
  verificado_em: "2026-09-02",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
