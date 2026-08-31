(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-110-a-caixa-aprendeu-a-corrigir-o-texto-de-uma-ideia",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "Segundo degrau: a parte que guarda as sugestoes ja sabe corrigir texto, e ja sabe guardar o que estava escrito antes",
  detalhe: "Este e o miolo da correcao que voce pediu hoje. Ele ainda nao tem botao — o botao e o proximo degrau, e ai voce vai poder usar. O que existe agora e a maquinaria: a parte do sistema que guarda as sugestoes aprendeu a trocar o nome e o texto de uma ideia, e aprendeu a nunca perder o que estava escrito antes.\n\nO QUE ELA FAZ, EM PORTUGUES: quando a correcao chegar, cada pedaco que mudou vira uma linha guardada com o texto velho, o texto novo, quem corrigiu e a data. Se voce corrigir o nome e o texto de uma vez, sao duas linhas. E essa linha nao pode ser editada nem apagada por ninguem — nem por mim, nem por um robo desta casa, nem por um comando direto no banco de dados: o proprio banco recusa. Eu medi isso tentando de verdade, pelas tres portas possiveis, e as tres foram recusadas.\n\nPOR QUE EU FIZ TANTA QUESTAO DISSO: voce escolheu que a correcao e calada, e eu concordo com a escolha. Mas calada sozinha seria perigosa. 'Calado' e 'sem prova' parecem a mesma coisa quando se le rapido, e sao opostos: sem a linha guardada, a escola poderia reescrever a fala de um aluno e ninguem conseguiria dizer o que ele tinha escrito. O dia em que um aluno reclamar do texto trocado e exatamente o dia em que essa prova faz falta.\n\nAS QUATRO TRAVAS QUE ENTRARAM JUNTO, e o motivo de cada uma:\n\n1. Ideia que voce apagou de vez nao volta por aqui. Corrigir o texto dela seria trazer de volta, por uma porta lateral, o conteudo que o apagar prometeu destruir.\n2. Valem as MESMAS reguas de quando o aluno escreveu: nome obrigatorio, ate 140 letras, e o texto do problema nao pode ficar vazio. Sem isso, a escola conseguiria gravar por dentro uma ideia que o proprio aluno nao teria conseguido criar.\n3. Salvar sem ter mudado nada e RECUSADO, com essa frase. Um 'pronto, corrigido' que nao gravou nada e o tipo de mentira pequena que faz voce parar de confiar na tela.\n4. Corrigir nao e a ideia ANDAR: ninguem recebe aviso, e o historico de fases da ideia nao ganha linha nenhuma. Se saisse aviso, 'calada' seria mentira ja no primeiro uso.\n\nFALTA A TELA. E o proximo degrau, e e o que voce vai ver.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/785 (consumidor do Rito de Contrato https://github.com/abundanciabr/sitesdoreino/pull/779, ja mergeado em 8965b478). PROVA VERMELHO->VERDE, sem rede: contra o codigo de origin/main o tests/test_correcao_de_texto.py nem coleta ('ModuleNotFoundError: No module named apps.core.correcao') e o tests/test_api_gestao.py da 7 failed / 38 passed; com o PR, 549 passed na celula inteira (eram 518, entao 31 testes novos). O append-only foi medido nos TRES degraus, incluindo UPDATE e DELETE em SQL cru recusados pelo Postgres ('DatabaseError: append-only') e a CheckConstraint que recusa correcao que nao corrige nada. A promessa de correcao calada tem guarda pela porta do ALUNO: a pagina dele mostra o texto novo e nenhuma marca. ci/contract_freeze.py sugestoes PASS (identico ao congelado, 1062 linhas, 10 operacoes com autenticacao conferida na fonte). black --check limpo em 108 arquivos.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
