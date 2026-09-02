(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-003-o-motor-das-mensagens-automaticas-ganhou-as-tabelas",
  tipo: "entrega",
  quando: "2026-09-02",
  titulo: "O motor das mensagens automáticas ganhou o lugar onde vai guardar as sequências",
  detalhe: "Este é o segundo degrau da escada das mensagens automáticas, e ele é o alicerce: a parte do sistema que vai mandar boas-vindas e lembretes agora tem onde guardar as sequências, quem está em cada uma, o que foi enviado e o que foi barrado.\n\nO que ele NÃO faz, de propósito: não manda mensagem nenhuma, não escuta acontecimento nenhum e não agenda nada. Isso são os próximos dois degraus. Toda sequência nasce desligada, e nenhuma versão nasce publicada: nada que entrou aqui consegue mandar carta para um aluno, nem por acidente.\n\nQuatro promessas do plano deixaram de ser texto e viraram trava dentro do banco de dados. A mais importante: a mesma pessoa pode entrar de novo numa sequência que já terminou (quem sumiu em março, voltou e sumiu de novo em julho é alcançado nas duas vezes), mas nunca duas vezes ao mesmo tempo. Era esse o defeito que a consultoria de 31/08 encontrou, e ele bloqueava uma das quatro sequências que você escolheu.\n\nOutra promessa que virou trava: depois de publicada, uma versão de sequência não muda mais. Você vai poder trocar a frase de boas-vindas numa terça à noite, e quem já está no meio da sequência continua vendo o texto com que entrou. Antes disso era só uma boa intenção escrita; agora o banco recusa a alteração.\n\nProva: 53 testes verdes na célula (eram 20). E, para provar que as travas realmente mordem, cada uma foi quebrada de propósito, uma por vez, e o teste correspondente ficou vermelho. Uma quarta quebra me contradisse: uma explicação minha sobre o comportamento do banco estava errada, foi medida, e o texto errado saiu do código antes de virar lenda.\n\nDe passagem, uma correção no plano: ele dizia oito tabelas e a lista sempre teve nove.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/845",
  verificado_em: "2026-09-02",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
