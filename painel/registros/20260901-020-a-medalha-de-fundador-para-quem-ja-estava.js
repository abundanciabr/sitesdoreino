(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-020-a-medalha-de-fundador-para-quem-ja-estava",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "A medalha de Fundador ja pode ser dada, e falta so voce dizer a quem",
  detalhe: "A escola agora consegue dar a medalha de Fundador (aquela que diz \"estava aqui no começo de tudo\") para quem entrou antes de a gamificação existir. Até hoje a medalha estava no banco, com nome e descrição prontos, e não havia caminho nenhum para entregá-la a alguém.\n\nO QUE FICA FALTANDO, E É COM VOCÊ (duas coisas, e as duas são de um minuto):\n\n1. LIGAR A MEDALHA. Toda a economia do site nasceu desligada de propósito, e ligar é decisão sua, na sua tela em /admin/economia/, para ficar registrado com data. Enquanto ela estiver desligada, o comando se recusa a fazer qualquer coisa e explica o motivo. Isso é o desenho, não um defeito.\n\n2. DIZER QUEM É FUNDADOR. Esta é a parte que nenhuma máquina consegue responder no seu lugar, e vale entender por quê: a parte do site que cuida das conquistas só conhece uma pessoa depois que ela ganha o primeiro ponto ou abre a página de conquistas pela primeira vez. Se eu perguntasse a ela \"quem estava aqui no começo?\", a resposta seria \"quem chegou por último\", com toda a cara de certa. Quem sabe quem estava lá é você.\n\nCOMO VAI FUNCIONAR quando você quiser usar: você me passa a lista de quem é fundador, eu rodo primeiro em modo ensaio (que só mostra na tela quem receberia, quem já tem e quem o site ainda não conhece, sem escrever nada) e te mostro. Se a lista estiver certa, eu rodo de verdade. Cada pessoa da lista ganha os 25 Cristais da medalha e recebe o aviso no sininho.\n\nE se a lista chegar pela metade, tudo bem: rodar de novo é seguro por construção. Ninguém ganha duas medalhas nem 50 Cristais, porque quem impede isso é o próprio banco de dados, não a memória de quem roda. Dá para acrescentar um nome esquecido amanhã sem ninguém precisar lembrar o que já rodou.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/826. Suíte da célula gamificacao de 230 para 247 testes, make ci verde (lint, type, testes, freeze de contrato). As quatro travas do comando foram provadas por mutação, uma a uma: tirar a recusa da medalha desligada, fazer o ensaio escrever, o relatório parar de olhar o retorno de conceder() e o id desconhecido virar pessoa inventada deixam vermelho, cada um, exatamente o teste que o guarda. Arquivo restaurado volta a 17 de 17. ci/travessao.py PASS. Degrau 22 da escada da gamificação, TAR-094.",
  verificado_em: "2026-09-01",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: "A medalha continua existindo no banco sem chegar a ninguém, exatamente como estava antes. Nada quebra, e ninguém fica sabendo que ela existe. O único custo é o tempo passando: quanto mais gente entra, menos especial fica a medalha que diz \"estava aqui no começo\".",
  recomendacao: "Ligar a medalha em /admin/economia/ e me passar a lista de quem estava aqui no começo, mesmo que seja curta e mesmo que esteja incompleta. Rodar em pedaços é seguro por desenho, então não vale a pena esperar a lista ficar perfeita.",
  reversivel: false,
  impacto: "baixo"
});})();
