(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-131-o-robo-nao-fica-mais-parado-olhando-a-fila",
  tipo: "resposta",
  quando: "2026-08-31",
  titulo: "O robô parou de ficar olhando a fila: o PR #801 entrou e o deploy foi verde",
  detalhe: "Está no ar a correção do 'monte de Aguardando' que você viu na tela. O PR #801 pousou (merge d337030d) e o deploy rodou verde logo depois (run 33449829964, 'success', conferido pela API do GitHub, não por um pipe). O que muda na prática: o robô não fica mais parado esperando a fila chamar o PR dele (eram cerca de 8 dos 12 minutos de espera de cada tarefa, puro tempo morto), ele segue trabalhando enquanto o deploy roda, e para de repetir 'Aguardando' a cada batimento. O que NÃO mudou, de propósito: ele continua conferindo o veredito do deploy antes de dizer 'está no ar' — essa é a trava contra falso-verde, e afrouxá-la seria trocar barulho por mentira. Vale registrar que o diagnóstico que eu te dei primeiro estava errado: eu disse que a fila estava cheia de robôs, sem medir. Medindo os 40 PRs do dia, a fila entrega em 8,4 minutos na mediana e roda 326 vezes por hora — ela nunca foi o problema, e nada leva horas (o pior do dia levou 34 minutos). O caso inteiro, com os dois erros meus registrados junto, está em armadilhas/258.",
  autoridade: "sonda",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/actions/runs/33449829964",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: "20260831-128-o-robo-parava-de-trabalhar-para-olhar-a-fila",
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
