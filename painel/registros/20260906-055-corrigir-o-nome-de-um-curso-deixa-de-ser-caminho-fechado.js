(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-055-corrigir-o-nome-de-um-curso-deixa-de-ser-caminho-fechado",
  tipo: "entrega",
  quando: "2026-09-06",
  titulo: "Corrigir o nome de um curso deixa de ser um caminho fechado",
  detalhe: "Conserto de um defeito MEU, entregue ha uma hora. O comando que cadastra um curso se recusa a renomear em silencio, e isso esta certo: o nome sai na lista de escolher, e trocar e decisao sua. Mas a recusa mandava voce 'mudar pelo painel do catalogo', e ESSE PAINEL NAO EXISTE. Nenhuma tela do site mexe em produto. A mensagem apontava para o vazio.\n\nAGORA ela ensina o comando exato, ja pronto para colar, e a opcao de renomear troca o nome dizendo qual era o antigo: quem renomeia por engano precisa saber o que tinha antes para desfazer.\n\nPOR QUE ISSO IMPORTA PARA VOCE: se voce cadastrar o Curso 2 e nao gostar do nome que ele aparece na lista, agora tem como trocar. Antes, nao tinha.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1198 (PR #1198). Medido: nenhuma rota da celula admin fala de produto ou catalogo, e o unico caminho que cria Product e comando de terminal. Suite da celula catalogo em PostgreSQL real: 92 passed (antes: 83). Prova por mutacao, as duas caindo na assercao: renomear sem ser pedido (assert 'Outro Nome Qualquer' == 'Profissional') e a recusa deixando de ensinar o comando. A segunda sabotagem, na primeira tentativa, quebrou a sintaxe e derrubou os 11 testes sem provar nada; refeita com sintaxe valida conferida por ast.parse. black --check: 35 arquivos, nenhum a reformatar. Freeze do catalogo: PASS.",
  verificado_em: "2026-09-06",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
