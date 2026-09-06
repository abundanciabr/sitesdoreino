(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-105-o-projeto-mandava-voce-procurar-o-dns-no-lugar-errado",
  tipo: "entrega",
  quando: "2026-09-06",
  titulo: "O projeto mandava voce procurar o DNS numa conta de Cloudflare que nunca existiu",
  detalhe: "Ligando o e-mail hoje, medi de quem sao os nameservers do meshcraft.top: pixel e byte.dns-parking.com, que sao da HOSTINGER. O projeto dizia Cloudflare em dois lugares do script que liga o e-mail, e um deles e impresso na SUA tela da VPS, no fim do processo. Voce seguiu a instrucao errada e foi procurar onde nao havia nada.\n\nCorrigido para Hostinger, com os nomes reais dos registros (o Brevo nao pede SPF: pede brevo-code, dois DKIM e _dmarc). Toca infra/, caminho protegido, entao o pouso espera o seu aval.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1244",
  verificado_em: "2026-09-06",
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
