(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-095-a-home-de-quem-nunca-pediu-deixou-de-ser-um-beco",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "A home de quem nunca pediu deixou de ser um beco — agora ela convida a pedir entrada",
  detalhe: "VOCE ACHOU O DEFEITO COM A SUA PROPRIA CONTA, de novo. Entrou no meshcraft.top, leu 'Em breve teremos muitas novidades' e nao tinha para onde ir. O formulario de pedir entrada existia inteiro na Caixa o tempo todo — so que ninguem chega a um endereco que a tela nao mostra.\n\nO QUE MUDA: quem entrou com o Google e nunca pediu nada passa a ver, na home, 'Quer estudar no Meshcraft? Peca sua entrada — a equipe decide quem entra' e um botao 'Pedir entrada' que leva ao formulario.\n\nISTO REVERTE UMA DECISAO SUA, E A REVERSAO E SUA TAMBEM. Em 28/08 voce escolheu, entre tres opcoes, que quem nunca pediu nada nao veria nada sobre a escola na home — e a escolha tinha motivo: ate ali o caminho da Caixa aparecia para TODO MUNDO, e quem nao era aluno clicava para receber um 'nao encontramos matricula'. A recusa curava aquele defeito e criava este: trocou uma porta que batia na cara por uma parede sem porta nenhuma. A lei nova esta em docs/decisoes/DECISAO-o-beco-de-quem-entrou-e-nunca-pediu.md.\n\nO CUIDADO QUE FOI TOMADO: o convite so aparece para quem a peca que guarda os alunos CONFIRMOU nunca ter pedido nada. Se ela estiver fora do ar, a home volta a nao oferecer nada — porque nesse caso ela nao sabe, e convidar um ALUNO a pedir a entrada que ele ja tem seria o defeito de 28/08 de cabeca para baixo.\n\nESTA E A FATIA 1 DE 5. Voce aprovou hoje, depois do mapa da jornada do aluno, as cinco arestas: (1) este beco, (2) a tela viva da jornada no painel, (3) busca e filtro na lista de alunos, (4) cadastrar alguem a mao, (5) avisar pelo sino quando a situacao muda. Cada uma vem no proprio PR.\n\nSOBRE A SUA CONTA DE TESTE: a ficha dela foi APAGADA de verdade, no dia em que apagar ainda era possivel — por isso ela nao aparece como ex-aluna, e sim como quem nunca esteve aqui. Depois deste PR no ar, voce abre meshcraft.top com a sua conta, clica em 'Pedir entrada', preenche, e se libera em /admin/escola/alunos/. Dai em diante o teste de sair e voltar roda no mundo novo, onde ficha nao se apaga.",
  autoridade: "github",
  evidencia: "PR #503. Vermelho->verde MEDIDO: sem a mudanca no template a celula funil NAO SOBE — o validador i18n e fail-closed (D4) e reprova o boot com 'landing.pedir_entrada: definida e nao usada em nenhum template'. Com a mudanca, 356 passed em services/funil (pytest), black --check 36 files unchanged, e ci/ci.py --apenas muralhas PASS nos 8 portoes (cerca-de-celula: 1 celula tocada: funil). Quatro guardas novos, entre eles test_nao_saber_nao_convida_ninguem, que trava o erro simetrico.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null
});})();
