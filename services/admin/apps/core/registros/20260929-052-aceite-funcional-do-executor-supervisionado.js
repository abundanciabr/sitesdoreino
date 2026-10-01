(function(){(window.REGISTROS=window.REGISTROS||[]).push({
arquivo:"20260929-052-aceite-funcional-do-executor-supervisionado",
tipo:"medicao",quando:"2026-09-29",
titulo:"Executor supervisionado reconciliado após publicação",
detalhe:"No Windows do usuário, o piloto A foi interrompido e retomou a mesma sessão até somar 10; o piloto B somou 18 sem alterar os quatro arquivos de A. Após a integração da revisão 3a7bb67c1068524ec3dfc68aeae721cb00e9a4b7, o comando reconciliar revalidou a tentativa B existente, a posse e o encerramento dos processos: resultado_recebido e exit 0. A medição pós-integração foi uma reconciliação, não uma nova criação ou retomada. O modelo Luna medium é seleção local; o backend não emitiu atestado.",
autoridade:"sessao",
evidencia:"https://github.com/abundanciabr/sitesdoreino/pull/2334 https://github.com/abundanciabr/sitesdoreino/actions/runs/36609546273 Execução local Windows de python ci/executor_codex.py reconciliar às 18:15 UTC, com fonte da revisão integrada 3a7bb67c1068524ec3dfc68aeae721cb00e9a4b7: resultado_recebido, exit 0, processos encerrados, soma 18 e quatro hashes de A preservados. Rastro operacional privado SHA256 0B2C739CBF78CF7DF351CBC6E6396696B5884BA40ACD9625CEBAA27635E48B6A; estado preservado SHA256 DB498E787DF8AAA54290841550BB9A57631305A969CD45F874A3328ED4CBDB7B. O deploy comprova publicação do commit, não execução do Codex na VPS.",
verificado_em:"2026-09-29",precisa_do_dono:false,
responde_a:"20260929-030-ci-executar-e-retomar-codex-isolado",relacao:"comentario",
tarefa:"TAR-964",gravidade:"verde",frente:"fabrica",area:"ci",
entrega:{
  pr:"https://github.com/abundanciabr/sitesdoreino/pull/2334",
  revisao:"c692850018d560e1475dfeb546bd88b868492103",
  arvore:"5e2be688224311c2bebf1098bc44cfc49d0a46b7",
  integracao:"3a7bb67c1068524ec3dfc68aeae721cb00e9a4b7",
  publicacao:"PUBLICADO",
  publicacoes:["https://github.com/abundanciabr/sitesdoreino/actions/runs/36609546273"]
},
aceite_funcional:{
  resultado:"PASS",
  criterio:"A implementação integrada conserva e reconcilia a tentativa supervisionada B com posse válida, resultado terminal e processos encerrados; a jornada dos pilotos confirma retomada da mesma sessão em A e isolamento dos quatro arquivos de A durante B.",
  evidencia:"Comando local Windows python ci/executor_codex.py reconciliar às 18:15 UTC sobre tentativa B já criada: resultado_recebido, exit 0, processos_encerrados true, soma 18; A permaneceu com seus quatro hashes e soma 10. Fonte do executor e dependências da revisão 3a7bb67c1068524ec3dfc68aeae721cb00e9a4b7; deploy-celula 36609546273 concluído às 18:11 UTC. Reconciliação pós-merge, sem nova criação ou retomada nesse passo. Rastros privados SHA256 0B2C739CBF78CF7DF351CBC6E6396696B5884BA40ACD9625CEBAA27635E48B6A e DB498E787DF8AAA54290841550BB9A57631305A969CD45F874A3328ED4CBDB7B.",
  revisao:"3a7bb67c1068524ec3dfc68aeae721cb00e9a4b7",
  ambiente:"producao"
},
vence_em_dias:null,se_eu_nao_decidir:null,recomendacao:null,reversivel:null
});})();
