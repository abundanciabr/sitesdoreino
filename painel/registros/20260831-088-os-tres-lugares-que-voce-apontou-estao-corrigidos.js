(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-088-os-tres-lugares-que-voce-apontou-estao-corrigidos",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "Passo 5 de 5: os tres lugares que voce apontou estao corrigidos",
  detalhe: "PODE CONFERIR NOS TRES ENDERECOS QUE VOCE ME MANDOU.\n\n1. Em /admin/escola/alunos/ a caixa 'Reembolsados' dizia 'devolveram o dinheiro e CONTINUAM com acesso'. Agora diz que nao entram mais em nada, e que a ficha continua ai para voce religar com um clique se tiver sido engano.\n\n2. Em /admin/escola/jornada/ o 'Reembolsado' MUDOU DE LUGAR no mapa. Ele estava na faixa 'Dentro da escola', com a tarja de quem entra; foi para a faixa 'Depois', com a tarja de quem nao entra.\n\nEsse detalhe merece um paragrafo, porque foi o cuidado que carregou esta parte: se eu tivesse trocado so o TEXTO e deixado o cartao onde estava, a tela diria a verdade na frase e o contrario no desenho. E o desenho voce le primeiro. A faixa e a cor sao a resposta visual a pergunta 'essa pessoa entra?', e elas conseguem mentir sozinhas. Escrevi um teste que mede a POSICAO do cartao, e nao a palavra dentro dele.\n\n3. Em /docs/como-funciona-a-entrada e /docs/jornada-do-aluno, as duas paginas que qualquer aluno le, o texto passou a dizer que o reembolso desfaz a matricula e o acesso acaba junto. Tudo sem travessao, como voce mandou em 30/08.\n\nMAIS DUAS LINHAS QUE NAO SAO ENFEITE. O rotulo do formulario onde VOCE escolhe a situacao de alguem agora diz 'Reembolsado, devolveu o dinheiro e perde o acesso' — e esse e o texto que voce le no segundo em que decide. E o prontuario aprendeu a palavra 'reembolsado': sem ela, ele mostraria 'nao sei dizer' sobre uma pessoa que voce mesmo tinha acabado de reembolsar.\n\nISTO FECHA O SEU PEDIDO. Foram cinco entregas: a lei, o combinado entre as pecas, a porta que decide o acesso, a tela que explica para a pessoa, e estas telas suas. O comportamento ja tinha mudado no passo 3; este passo e o que faz o que esta ESCRITO combinar com o que o sistema FAZ — que era exatamente a sua queixa.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/764 — services/admin/apps/core/views.py (a caixa de contagem, a parada da jornada mudando de faixa com acesso: False, o rotulo do formulario e a sexta categoria do prontuario), services/admin/tests/test_jornada_na_tela.py (dois guardas: so o aluno entra, e o reembolsado esta na faixa certa), documentos/como-funciona-a-entrada.md e documentos/jornada-do-aluno.md. Medido nesta sessao: 515/515 da suite da celula admin; portao do travessao PASS com 75 arquivos de texto publico inspecionados e nenhum travessao novo; black limpo. Provas por mutacao, com a sabotagem conferida antes do resultado: devolver acesso: True ao reembolsado = 1 vermelho; mover a parada de volta para a faixa 'Dentro da escola' = 2 vermelhos. A escada completa do pedido: PRs 756 (a lei), 758 (o contrato), 762 (a celula alunos), 763 (a celula sugestoes) e 764 (este).",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
