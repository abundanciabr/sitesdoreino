(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-032-nenhuma-area-nova-do-site-nasce-sem-menu-e-sem-rodape",
  tipo: "entrega",
  quando: "2026-09-02",
  titulo: "Nenhuma área nova do site nasce mais sem menu e sem rodapé",
  detalhe: "Os dois passos anteriores consertaram a página de Conquistas. Este conserta a causa, para o mesmo problema não voltar em outra área.\n\nO que estava acontecendo: quando o menu e o rodapé nasceram, em 31 de agosto, eles foram colocados nas áreas que já existiam naquele dia. As Conquistas foram ao ar um dia depois, e não havia nada no sistema que perguntasse \"esta área nova mostra o menu e o rodapé?\". As travas antigas estavam todas verdes e todas certas: elas cuidam de uma área cada uma, e nenhuma delas sabia que as Conquistas existiam.\n\nAgora existe uma trava que olha o site inteiro. Ela pega a lista de páginas do próprio mapa do site (o mesmo que você vê em /admin/mapa/) e, para cada área que serve página a gente, pergunta se ela mostra as duas peças. Área que não mostra e não tem justificativa escrita faz o sistema recusar a mudança. Como a lista vem do mapa e não é escrita à mão, área nova entra na conta sozinha no dia em que nascer.\n\nA trava também recusa o contrário: uma justificativa escrita para algo que já foi consertado. Isso evita que um aviso velho fique mandando alguém procurar um problema que não existe mais.\n\nO que ainda falta, e ficou escrito com o motivo de cada um: a Caixa de Sugestões (que tem rodapé próprio, e trocar pelo do site é decisão sua de visual), a biblioteca de documentos, o quiz (que está de pé mas sem nenhum quiz publicado) e a área de compra (que está parada por decisão sua). Nenhum deles é esquecimento agora: são quatro linhas escritas, cada uma com a razão.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/870",
  verificado_em: "2026-09-02",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
