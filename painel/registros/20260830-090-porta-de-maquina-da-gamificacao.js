(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-090-porta-de-maquina-da-gamificacao",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "A parte das conquistas voltou a aceitar trabalho: a porta de máquina nasceu",
  detalhe: "A parte do site que vai guardar XP, níveis, sequência e missões estava TRAVADA: o contrato dela — a lista do que ela promete responder a quem perguntar — tinha sido fechado com você presente, mas a porta que cumpre essa promessa ainda não existia. O portão de conferência não conseguia nem medir: dizia \"não sei fazer isso\" e parava. Enquanto durasse, qualquer robô que mexesse nessa parte do site batia na mesma parede, e nenhum trabalho seguinte andava.\n\nAgora a porta existe e a conferência passa. O portão saiu de \"não consegui medir\" para \"idêntico ao contrato, 263 linhas conferidas\", e mais: ele confirmou na fonte que as duas operações exigem senha de máquina.\n\nO que a porta faz, em português: (1) o fórum pergunta o nível e o título de vários alunos de uma vez, para estampar a etiqueta ao lado do nome de quem escreveu — e nunca sai e-mail, nome, nem o XP de outra pessoa; (2) o próprio aluno vê o XP dele, a sequência da semana e as missões. Quem não entrou recebe \"não está logado\", nunca uma tela de erro.\n\nO que vai parecer defeito e não é: o robô de publicação desta parte vai ficar VERMELHO neste merge. O servidor ainda não sabe que essa parte do site existe — ela só é declarada lá num passo de infraestrutura que é outro trabalho. Some sozinho quando esse passo acontecer.\n\nO que fica esperando esse mesmo passo de infraestrutura: uma configuração chamada SITE_ID precisa entrar no arquivo de ambiente dessa parte. Sem ela a etiqueta some para todo mundo em silêncio — a porta foi escrita para reclamar alto no registro do servidor quando isso acontecer, mas quem coloca a linha é o trabalho de infraestrutura.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/656",
  verificado_em: "2026-08-30",
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
