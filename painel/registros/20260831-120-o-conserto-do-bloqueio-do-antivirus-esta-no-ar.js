(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-120-o-conserto-do-bloqueio-do-antivirus-esta-no-ar",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "O conserto do bloqueio do antivírus está no ar, com prova conferida de fora",
  detalhe: "Fecha o incidente do registro 20260831-111 (o Malwarebytes bloqueando o site por 'excesso de solicitação de notificações').\n\nO QUE FOI CONFERIDO, na ordem: o PR 786 pousou pela pista (merge b56c501d), o deploy da célula funil terminou verde, e o arquivo servido pelo PRÓPRIO site em meshcraft.top foi lido de fora: o caminho automático de pedido de permissão não existe mais nele, e a versão nova (com a marca da armadilha 257) é a que está chegando aos visitantes.\n\nCOMO FICA PARA O ALUNO: quem entra na conta vê um convite educado do site, com o botão 'Ligar os avisos'. A caixa oficial do celular só abre depois do toque. Nenhum pedido abre mais sozinho, em navegador nenhum, e é isso que tira o site do radar dos antivírus.\n\nSE ALGUÉM AINDA VIR O BLOQUEIO: é memória local do programa de segurança de quem já tinha visitado antes do conserto. Abrir o site e clicar em 'Continuar nesse site' uma vez resolve; visitante novo não deve ver bloqueio nenhum.",
  autoridade: "sessao",
  evidencia: "Merge b56c501d2ce30a81de2f1ffe407c9e5ab8cfdced (PR https://github.com/abundanciabr/sitesdoreino/pull/786). Run deploy-celula 33446676523, veredito por gh run view --json status,conclusion = completed success. Prova de fora: curl em https://meshcraft.top/static/funil/avisos.js devolve 0 ocorrências de 'abreSozinho' e 2 de 'armadilhas/257'.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: "20260831-111-o-antivirus-bloqueou-o-site-e-o-pedido-de-aviso-virou-botao",
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
