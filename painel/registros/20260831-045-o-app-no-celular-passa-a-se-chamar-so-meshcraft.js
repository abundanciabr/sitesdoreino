(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-045-o-app-no-celular-passa-a-se-chamar-so-meshcraft",
  tipo: "decisao",
  quando: "2026-08-31",
  titulo: "O app no celular passa a se chamar so Meshcraft",
  detalhe: "Assim que o site virou app instalavel, eu fui conferir de fora como ele apareceria no celular de um aluno e achei uma coisa que ninguem tinha reparado: o site esta cadastrado como 'Meshcraft (site de testes)', um nome de quando ele nasceu. E esse nome ia virar o nome do ICONE na tela de inicio de quem instalasse. No celular, nome comprido e cortado no meio: o aluno veria algo como 'Meshcraft (site de te...'.\n\nVoce escolheu 'Meshcraft', so isso, e e o que entra.\n\nONDE ISSO MUDA: no cadastro do site, que e um arquivo unico e declarado. O deploy leva a mudanca ate o catalogo de producao sozinho. Quem ja instalou o app antes desta mudanca pode continuar vendo o nome antigo no icone ate reinstalar, porque o nome fica gravado no aparelho na hora da instalacao. Como o app nasceu hoje e ainda nao foi anunciado, isso na pratica nao afeta ninguem.\n\nE valeu a licao: foi olhar o site DE FORA, como um visitante olharia, que encontrou isso. Nenhum teste pegaria, porque o nome nao esta no codigo, esta no cadastro.",
  autoridade: "mantenedor",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/726. Medido ao vivo antes da mudanca: https://meshcraft.top/manifest.webmanifest?idioma=pt-br respondia 200 com name 'Meshcraft (site de testes)'.",
  verificado_em: "2026-08-31",
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
