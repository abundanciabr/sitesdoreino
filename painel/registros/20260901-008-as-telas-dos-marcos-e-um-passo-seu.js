(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-008-as-telas-dos-marcos-e-um-passo-seu",
  tipo: "pendencia",
  quando: "2026-09-01",
  titulo: "As telas dos marcos estao prontas, e falta uma linha sua para abrir a fila da equipe",
  detalhe: "AS DUAS TELAS EXISTEM AGORA.\n\nA do aluno fica em meshcraft.top/conquistas/marcos: a lista dos marcos que a escola abriu, e para cada um o estado dele. Conquistado, esperando a escola olhar (com a data limite), devolvido (com o motivo escrito em portugues e o botao de mandar de novo), ou disponivel para enviar. Ela nao tem numero nenhum, de proposito: marco vale zero ponto, e um contador ao lado dele ensinaria o aluno a perseguir o numero em vez da coisa.\n\nESSA TELA CONSERTA UM BURACO que eu tinha declarado na entrega anterior: devolver um pedido nao gera aviso no sininho, porque a regra da escola e que so boa noticia vira aviso. Sem essa pagina, o aluno esperaria para sempre por uma resposta que ja chegou. Agora ele ve.\n\nA da equipe fica em meshcraft.top/conquistas/interno: a fila, com o mais urgente em cima, e dois botoes por pedido. Aceitar registra a conquista no nome da pessoa e avisa ela na hora. Devolver pede o que falta, escolhendo de uma lista curta, e nao avisa ninguem.\n\nO QUE PRECISA DE VOCE, e e uma linha so: a fila da equipe hoje nao abre para NINGUEM, nem para voce. Isso e de proposito, e e a parte mais importante do desenho: quem pode dizer 'sim, o primeiro cliente desta pessoa aconteceu' e uma lista curta de nomes que so existe dentro do servidor. Enquanto a lista estiver vazia, quem abrir a pagina ve, em portugues, que nao esta nela.\n\nPara entrar na lista, cole isto DENTRO DA VPS (a janela cujo endereco comeca com deploy@srv ou root@srv), trocando o e-mail pelo seu:\n\ncurl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-equipe-da-gamificacao.sh -o /tmp/e.sh && bash /tmp/e.sh SEU-EMAIL@exemplo.com\n\nO que ele faz: pergunta a parte do site que guarda as pessoas qual e o numero interno do seu e-mail (e se recusa a continuar se nao achar, em vez de inventar), escreve esse numero na lista, reinicia a parte das conquistas e confere que ela voltou de pe. Guarda uma copia de seguranca antes de mexer. Rodar duas vezes nao estraga nada e nao remove ninguem. Se algo estiver estranho, ele para e escreve PAROU POR SEGURANCA, sem alterar nada.\n\nSE VOCE NAO RODAR: nada quebra. O aluno continua podendo mandar a prova, e ela fica esperando na fila ate alguem da equipe poder olhar.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/814. Suite da celula 202 passed (eram 191; 11 testes novos). PROVA VERMELHO->VERDE POR ASSERCAO (armadilhas/195): com a fechadura da equipe devolvendo sempre 'pode', os dois guardas acusam 'assert 200 == 403' (a pessoa fora da lista e a lista vazia); reposta a linha, 11 passed. ci/mapa_do_site.py PASS (143 rotas medidas, 143 declaradas, as 4 novas no mapa); ci/travessao.py PASS nas duas telas novas; ci/mapa_de_celulas.py PASS; black limpo; bash -n limpo no script de provisionamento.",
  verificado_em: "2026-09-01",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: "A fila da equipe continua fechada para todo mundo. Os alunos conseguem mandar a prova de um marco, mas ninguem consegue conferir e conceder, entao nenhum marco fica registrado.",
  recomendacao: "Rode a linha quando quiser abrir a fila, com o seu e-mail. Leva menos de um minuto e e reversivel: sair da lista e editar uma linha do arquivo no servidor.",
  reversivel: true,
  impacto: "medio"
});})();
