(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-076-as-tres-travas-existem-mas-ainda-nao-estao-na-lista-oficial",
  tipo: "nota",
  quando: "2026-08-30",
  titulo: "As tres travas da gamificacao ja funcionam, mas ainda nao estao na lista oficial que as vigia",
  detalhe: "As tres promessas que voce fez ao aluno viraram trava de verdade hoje: nada se compra com dinheiro de verdade, enfeite e so enfeite, e aula nunca fica trancada atras de ponto. Nao sao frases num documento. Sao regras dentro do banco de dados, mais tres testes que o robo quebrou de proposito para mostrar o alarme tocando.\n\nFalta um carimbo, e ele importa. O projeto tem uma lista oficial de garantias, e existe um guarda cujo unico trabalho e conferir se cada garantia dessa lista ainda tem o teste que a defende. As tres travas novas ainda nao estao nessa lista. Na pratica: elas protegem hoje, mas se um dia alguem apagar o arquivo de teste por engano, nada acusa a falta.\n\nO robo que as construiu nao fez o carimbo por um bom motivo, e vale registrar: o arquivo da lista oficial e um dos poucos que exigem autorizacao especial para mexer, e ele nao tinha essa autorizacao no despacho dele. Em vez de contornar em silencio, ele avisou em texto. Foi o comportamento certo.\n\nJa virou tarefa no balcao, com a autorizacao vindo da propria lei da celula que voce aprovou hoje: ela diz que os tres invariantes nascem como teste no CI e nunca se flexibilizam. Declarar e cumprir a lei, nao ampliar escopo. A prova exigida vai nos dois sentidos: o guarda aprovando com os tres declarados, e o guarda RECLAMANDO quando um deles e retirado.\n\nNada disso espera por voce.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/638 (este PR, que cria a TAR-042). As tres travas vieram no PR https://github.com/abundanciabr/sitesdoreino/pull/636 (TAR-035), com prova de sabotagem em cada uma: campo de dinheiro real no cosmetico derruba a assercao do invariante 1 e a remocao da restricao do banco derruba o teste que exige IntegrityError do PostgreSQL; multiplicador de XP no cosmetico derruba o invariante 2; campo de aula na definicao de nivel derruba o invariante 3 por tres angulos. Desfeitas as sabotagens: 10, 5 e 4 verdes. A lacuna foi reportada em texto pelo proprio robo, e a regra que a torna relevante e a regra 5 de ci/guarda_dos_guardas.py.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
