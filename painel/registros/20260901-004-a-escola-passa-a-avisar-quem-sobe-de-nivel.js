(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-004-a-escola-passa-a-avisar-quem-sobe-de-nivel",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "A escola passa a avisar quem sobe de nivel (a parte das conquistas era muda)",
  detalhe: "Este e o degrau que voce escolheu como proximo: as comemoracoes.\n\nCOMO ERA ATE HOJE: o aluno ganhava ponto e o sistema ficava calado. Subir de nivel so 'acontecia' se a pessoa resolvesse abrir a pagina de conquistas por conta propria. Quem nao abrisse nunca sabia.\n\nCOMO FICA: subir de nivel avisa de duas formas ao mesmo tempo, e as duas precisam existir porque alcancam pessoas diferentes. Quem esta com o site aberto ve a comemoracao na tela; quem nao esta recebe o aviso no sininho quando voltar. As duas sao escritas no MESMO instante em que o ponto e creditado, dentro da mesma operacao: se o credito for desfeito, o aviso vai junto e nunca sobra festa de uma coisa que nao aconteceu.\n\nA REGRA QUE EU FIZ QUESTAO DE TRAVAR NO CODIGO: so boa noticia vira aviso. Nivel que CAI (um ponto estornado, um conteudo moderado, uma correcao da equipe) nao gera aviso nenhum. Isso e lei da escola, e a razao e de produto: cobrar pelo que se perdeu esta na lista das coisas proibidas da gamificacao. Para provar que a trava e real, eu quebrei ela de proposito e mostrei o teste ficando vermelho antes de conserta-la.\n\nE UMA SEGUNDA, mais sutil: consertar nao e comemorar. Existe um comando de manutencao que reconfere os numeros do perfil contra o historico. Um perfil atrasado 'sobe' quando e reparado, e sem cuidado isso mandaria uma carta de parabens por um fato de semanas atras, no relogio da manutencao. Ele agora repara em silencio.\n\nO QUE AINDA NAO SAI, e a ausencia foi MEDIDA, nao esquecida: das quatro comemoracoes previstas, so a de nivel tem fato de verdade hoje. Medalha, marco validado e destaque da semana nao saem porque nada na escola AINDA concede medalha, valida marco ou destaca uma obra (isso vem em degraus mais a frente). O caminho por onde elas vao sair ja esta aberto e testado; falta o acontecimento, nao o codigo.\n\nE UMA COISA QUE PRECISA DA SUA DECISAO UM DIA, sem pressa: o plano da gamificacao diz que o aviso deve ser 'no maximo um por dia, nunca depois das 20h'. Isso e regra de QUANDO INCOMODAR, e nao de o que aconteceu — e hoje nenhuma parte do sistema a cumpre. Eu deliberadamente NAO joguei o aviso fora na origem para respeita-la: jogar fora apagaria o fato para sempre, e a pessoa nao o veria nem no dia seguinte. Quando as comemoracoes comecarem a acontecer de verdade, vale voce me dizer se quer esse limite, e onde.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/811. Suite da celula 171 passed (eram 159; 12 testes novos). PROVA VERMELHO->VERDE POR ASSERCAO (armadilhas/195), duas sabotagens: (1) trocando 'subiu de nivel' por 'mudou de nivel' no motor, o teste do estorno acusa 'AssertionError: descer de nivel nao pode escrever carta nenhuma / assert 2 == 1'; (2) com um campo a mais nos dados da carta, a validacao contra o ARQUIVO do contrato congelado acusa 'Additional properties are not allowed (xp was unexpected)' — o teste le contracts/eventos/notificacao.devida.v1.json, nunca uma copia do formato dentro do teste. ci/travessao.py PASS, black limpo, YAML do compose carregado e o servico novo conferido campo a campo. Toca infra/ (CODEOWNERS) para acrescentar o processo que roda o relay: relay sem processo e codigo que ninguem executa.",
  verificado_em: "2026-09-01",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
