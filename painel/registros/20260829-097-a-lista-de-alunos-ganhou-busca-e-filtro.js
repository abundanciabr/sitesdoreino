(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-097-a-lista-de-alunos-ganhou-busca-e-filtro",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "A lista de alunos ganhou busca por nome, e-mail e turma — e um filtro de situacao",
  detalhe: "A TELA MOSTRAVA A ESCOLA INTEIRA DE UMA VEZ, na ordem de entrada. Com dois alunos isso e confortavel; com duzentos e rolagem cega. Agora ela tem um campo de procurar (nome, e-mail ou turma), um seletor de situacao (Ativo, Pausado, Ex-aluno, Reembolsado), a frase 'Mostrando 3 de 47' sempre que voce estiver filtrando, e um botao Limpar.\n\nA BUSCA IGNORA ACENTO E MAIUSCULA: procurar por 'acai' acha 'Acainite'. Sem isso, a busca so serviria para quem digita o nome exatamente como foi cadastrado — ou seja, para quem ja sabe onde a pessoa esta, que e justamente quem nao precisa procurar.\n\nO CUIDADO QUE CARREGA ESTA ENTREGA: os cartoes de contagem NAO seguem o filtro. Eles contam a escola inteira, sempre. Se seguissem, procurar por 'ana' faria o cartao dizer '1 aluno ativo' — e voce leria o numero da sua busca como o tamanho da sua escola.\n\nOUTROS TRES CUIDADOS, cada um com o proprio guarda: 'nao consegui perguntar' nunca vira 'nao ha ninguem'; quando a busca nao acha nada a tela diz 'nenhum dos 5 alunos casou com a sua procura' em vez de 'ainda nao ha nenhum aluno'; e um endereco com uma situacao que a tela nao conhece mostra TODOS, com aviso, nunca uma lista vazia.\n\nO SEU WHATSAPP (e o de todo mundo) FICA FORA DA BUSCA, de proposito. E o dado mais sensivel dessa tela, e um campo que casasse com ele convidaria a colar numeros de telefone no endereco do navegador — que fica gravado no historico e nos registros do servidor.\n\nFATIA 2 DE 5. A ordem trocou com a da tela viva da jornada: aquela precisa apontar para listas ja filtradas, e o endereco do filtro precisava existir antes. Faltam: a tela viva da jornada, cadastrar alguem a mao, e o aviso pelo sino quando a situacao muda.",
  autoridade: "github",
  evidencia: "PR #505. Vermelho->verde MEDIDO: sem a mudanca o arquivo de teste nem importa ('from apps.core.views import peneirar' -> ImportError). Com ela, 242 passed na celula admin (pytest contra postgres 17 local), black --check 45 files unchanged, e ci/ci.py --apenas muralhas PASS nos 8 portoes (cerca-de-celula: 1 celula tocada: admin). 16 guardas novos, entre eles test_os_cartoes_contam_a_escola_inteira_mesmo_filtrando e test_nao_consegui_perguntar_continua_sendo_nao_consegui_perguntar.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null
});})();
