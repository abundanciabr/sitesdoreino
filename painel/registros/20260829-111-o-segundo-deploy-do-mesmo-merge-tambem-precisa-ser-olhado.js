(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-111-o-segundo-deploy-do-mesmo-merge-tambem-precisa-ser-olhado",
  tipo: "nota",
  quando: "2026-08-29",
  titulo: "Lição: um merge que mexe em infra e no painel dispara DOIS deploys — os dois precisam ser conferidos",
  detalhe:
    "Um merge (o do PR #502, o conserto do www.meshcraft.top) tocou infra/ e " +
    "painel/ ao mesmo tempo, o que disparou os dois deploys da plataforma: " +
    "deploy-infra e deploy-celula. O deploy-infra deu um problema conhecido " +
    "de rede (a armadilha 127) e se corrigiu sozinho. O deploy-celula DO " +
    "MESMO MERGE também tinha ficado vermelho — só que por um motivo " +
    "diferente: ele se recusa a repetir quando um vizinho dele (o deploy-" +
    "infra) também está vermelho, para não publicar em cima de bagunça.\n\n" +
    "Isso quase passou batido: um merge seguinte, minutos depois, disparou " +
    "outro deploy-celula que saiu limpo e publicou a versão certa — por " +
    "sorte de tráfego, não porque alguém tivesse olhado. Se aquele tivesse " +
    "sido o último merge do dia, a célula teria ficado dormindo numa versão " +
    "velha sem ninguém perceber.\n\n" +
    "A regra que fica: merge que dispara os dois deploys (porque tocou infra " +
    "E painel/serviço no mesmo commit) exige conferir os DOIS runs — mesmo " +
    "quando o primeiro que você olhou já ficou verde. Está escrito em " +
    "armadilhas/178 para a próxima sessão não precisar redescobrir isso.\n\n" +
    "Verificado hoje: os dois deploys daquele dia estão verdes, e o site " +
    "responde certo por fora (www.meshcraft.top com certificado válido, " +
    "redirecionando para o domínio principal).",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/506",
  verificado_em: "2026-08-29",
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
