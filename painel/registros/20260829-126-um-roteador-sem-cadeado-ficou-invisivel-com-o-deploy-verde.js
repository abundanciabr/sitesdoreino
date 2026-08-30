(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-126-um-roteador-sem-cadeado-ficou-invisivel-com-o-deploy-verde",
  tipo: "incidente",
  quando: "2026-08-29",
  titulo: "Um endereco novo ficou invisivel por uma linha que faltou — e o deploy ficou verde as duas vezes",
  detalhe: "ERRO MEU, e vale contar porque a CLASSE dele e maior que o caso.\n\nO QUE ACONTECEU: ao publicar a area de documentos, o endereco publico (meshcraft.top/docs/) respondia 404. A causa foi uma linha que faltou na tabela de roteamento: o endereco novo nao declarou o CADEADO (o TLS). Sem essa linha, a peca que distribui as requisicoes simplesmente NAO CRIA aquele endereco — e o pedido cai na pagina comum do site, virando 404.\n\nPOR QUE DEMOROU A APARECER: tudo o que se olharia parecia certo. A regra estava no arquivo, o endereco estava escrito corretamente, a peca de destino existia, e o deploy ficou VERDE — duas vezes, inclusive reaplicado. E um endereco IRMAO, acrescentado no mesmo arquivo minutos depois por outra sessao (o /forum/), funcionava.\n\nO QUE ACABOU APONTANDO O DEDO foi comparar os cabecalhos de seguranca que o site devolve. Cada caminho deixa uma assinatura diferente: o /mapa-ia/ vinha com a assinatura da area administrativa, e o /docs/ vinha com a assinatura da pagina comum. Ou seja, quem respondia era o site, nao a area de documentos. Isso fechou o caso sem eu precisar entrar no servidor — o que eu nao posso fazer.\n\nO QUE FICOU PARA NAO SE REPETIR: um guarda no CI que reprova qualquer endereco declarado no HTTPS sem o cadeado, com prova nos dois sentidos (ele fica vermelho quando deve). E a armadilha 187, com o comando de uma linha que reconhece o sintoma de fora.\n\nA LICAO, em uma frase: um portao que valida CONFIGURACAO sem exercitar COMPORTAMENTO tem esse ponto cego — e a defesa e sempre a mesma, medir de fora o que o mundo recebe. O deploy verde nao e prova.",
  autoridade: "sessao",
  evidencia: "PR #560 (o conserto e o guarda) e a armadilha 187. MEDIDO em 29/08/2026: GET meshcraft.top/docs/ devolvia 404 com X-Frame-Options DENY e SEM Content-Security-Policy — identico aos cabecalhos da raiz do site (o funil) e diferente do irmao /mapa-ia/, que devolve SAMEORIGIN e o CSP da celula admin. A tabela em origin/main tinha o roteador (conferido por git show do commit de merge), o deploy-infra ficou 'success' nas duas execucoes, e a reaplicacao nao mudou nada — foi a comparacao de cabecalhos que localizou a causa. Depois do conserto: /docs/ = 200 com SAMEORIGIN. O guarda novo reprova nomeando o roteador quando a linha e removida.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null
});})();
