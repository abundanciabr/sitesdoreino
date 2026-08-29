(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-102-a-jornada-do-aluno-quatro-de-cinco-e-o-que-falta",
  tipo: "pendencia",
  quando: "2026-08-29",
  titulo: "Falta a quinta: avisar pelo sino quando a situacao de alguem muda — e ela precisa de uma decisao sua",
  detalhe: "QUATRO DAS CINCO ESTAO NO AR (PRs 503, 505, 507 e 508, todos com deploy verde): a home de quem nunca pediu deixou de ser um beco; a lista de alunos ganhou busca e filtro; a jornada do aluno virou tela viva em /admin/escola/jornada/; e da para cadastrar um aluno a mao.\n\nA QUINTA — voce muda a situacao de alguem e a pessoa recebe um aviso no sininho — NAO e mais uma tela. Ela esbarra em tres coisas que nao existem hoje, e uma delas e uma escolha sua:\n\n1. A parte que guarda os alunos so conhece as pessoas pelo E-MAIL. O sininho entrega por ID DE PLATAFORMA — o numero que a parte da entrada com o Google da a cada pessoa. Ninguem, hoje, sabe traduzir um do outro: a parte da entrada so responde 'quem e o dono deste biscoito de sessao?', nunca 'qual e o id de quem tem este e-mail?'.\n\n2. A parte que guarda os alunos nunca publicou aviso nenhum. Ela so ESCUTA eventos. Ganhar voz e uma peca nova (a 'caixa de saida' que a Caixa de Sugestoes ja tem).\n\n3. O tipo de aviso 'mudei a situacao de uma matricula' nao existe no contrato dos avisos — hoje so existe 'a sua ideia mudou de fase'.\n\nOS DOIS PRIMEIROS SAO O MESMO GARFO: ou a parte da entrada ganha uma porta nova que responde 'qual o id de quem tem este e-mail', ou a parte que guarda os alunos passa a gravar o id da plataforma na ficha desde o primeiro dia. Nenhuma das duas e obviamente melhor, e as duas mudam um contrato congelado — o que, pela lei do projeto (RITOS §3), exige VOCE presente na conversa.\n\nENTAO ESTA E A PENDENCIA: uma conversa curta com voce sobre esse garfo. Nada esta quebrado enquanto isso; so o aviso automatico e que nao existe, e a pessoa continua descobrindo a mudanca na proxima vez que abrir o site.",
  autoridade: "sessao",
  evidencia: "MEDIDO no codigo de origin/main em 29/08/2026: contracts/identidade.openapi.yaml tem exatamente duas operacoes (getSession e getSessionFull), as duas por cookie — nao ha porta por e-mail. services/alunos nao tem nenhum modelo de outbox (grep por outbox/publicar em services/alunos: zero; services/sugestoes tem OutboxEvent desde a migracao 0002). contracts/eventos/notificacao.devida.v1.json tem 'assunto' como enum de UM valor so: sugestao.status-alterado. celulas.yml declara alunos com 'consome: []'.",
  verificado_em: "2026-08-29",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "curso",
  vence_em_dias: null
});})();
