(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-053-o-bloco-de-colar-que-cria-os-dois-cursos",
  tipo: "entrega",
  quando: "2026-09-06",
  titulo: "O bloco de colar que cria os dois cursos e matricula todo mundo no primeiro",
  detalhe: "E o seu passo da lei de hoje, o unico pedaco que so acontece dentro do servidor. Uma linha so, sem argumento nenhum, e ele faz o resto.\n\nO QUE ELE FAZ: cadastra o curso 'Primeiros Dolares com Roblox' e o curso 'Profissional' (o do livro), e depois poe TODA matricula que ja existe apontando para o primeiro, que e o que essas pessoas compraram.\n\nELE DESCOBRE A ESCOLA SOZINHO e para quando nao pode adivinhar: se houver mais de uma, ele lista e ensina como dizer qual; se nao houver nenhuma, ele diz isso com o que conferir.\n\nANTES DE ESCREVER, ELE MOSTRA O NUMERO: roda uma vez so olhando, imprime quantas matriculas serao apontadas, e so entao escreve. Da para conferir que o numero aplicado e o numero anunciado.\n\nEU NAO RODEI NA VPS, e nao tenho como (o robo nao tem SSH). Rodei o roteiro inteiro aqui contra um docker de mentira, nos sete caminhos, e uma das recusas nasceu errada: a de 'nenhum site' mandava voce escolher de uma lista vazia. So apareceu porque a recusa foi rodada em vez de imaginada.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1195 (PR #1195), toca infra (caminho CODEOWNERS). bash -n: sintaxe OK. python ci/ci.py --apenas muralhas: RESULTADO PASS nos 13 portoes. Roteiro rodado contra um docker falso em 7 cenarios: caminho feliz completo com --site e --curso chegando inteiros nas duas passadas, e 6 recusas conferidas uma a uma (falta o servico alunos, criar_curso ausente, apontar ausente, dois sites, nenhum site, id do curso nao relido). Depende de #1194 e #1178 terem pousado e feito deploy; o script confere os dois e recusa com instrucao.",
  verificado_em: "2026-09-06",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
