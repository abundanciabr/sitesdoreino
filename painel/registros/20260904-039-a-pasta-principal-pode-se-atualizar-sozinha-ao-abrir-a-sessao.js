(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260904-039-a-pasta-principal-pode-se-atualizar-sozinha-ao-abrir-a-sessao",
  tipo: "pendencia",
  quando: "2026-09-04",
  titulo: "Você quer que a pasta principal do projeto se atualize sozinha ao abrir cada sessão?",
  detalhe: "Ela é de onde todo robô recebe o manual e de onde rodam os vigias, e só anda "
    + "quando alguém a atualiza à mão: hoje está 195 entregas atrás. O PR #973 fez os DADOS "
    + "dos vigias virem do publicado, mas o CÓDIGO deles ainda tem a idade da pasta. A regra "
    + "da casa proíbe robô de atualizá-la (é compartilhada, pode ter trabalho não guardado), "
    + "então a decisão é sua.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/973",
  verificado_em: "2026-09-04",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: "Nada quebra: cada conserto nos vigias demora dias para valer nas sessões, como hoje.",
  recomendacao: "Sim, com trava: ao abrir a sessão, se a pasta estiver na main e sem nada modificado, ela avança sozinha para o publicado; com qualquer arquivo mexido, não toca em nada e avisa.",
  reversivel: true,
  impacto: "medio"
});})();
