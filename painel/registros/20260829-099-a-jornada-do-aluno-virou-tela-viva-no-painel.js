(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-099-a-jornada-do-aluno-virou-tela-viva-no-painel",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "A jornada do aluno virou uma tela viva no painel — com quantas pessoas estao em cada ponto agora",
  detalhe: "VOCE PEDIU 'um tipo de mapa da jornada do aluno para que ficasse mais facil de gerencia-los'. Ele esta em meshcraft.top/admin/escola/jornada/.\n\nSAO QUATRO FAIXAS, na ordem em que uma pessoa as vive: Fora da escola, Pedindo entrada, Dentro da escola, Depois. Oito paradas ao todo, e cada uma responde tres coisas: quem esta ali, O QUE ESSA PESSOA VE no site, e como se sai daquele ponto. Mais o numero de gente que esta nele agora.\n\n'O QUE A PESSOA VE' E A METADE QUE IMPORTA. Um mapa que so nomeasse estados seria um desenho bonito — e o que fez voce pedir esta tela foi justamente nao saber o que esperar da tela de alguem que voce tinha removido.\n\nCADA PARADA TEM UM LINK que leva direto para a lista daquela situacao, ja filtrada. E por isso que a busca e o filtro (a entrega anterior) vieram antes: a diferenca entre um desenho e uma ferramenta e o link.\n\nA CONTA E UMA SO. Os numeros dessa tela e os numeros da lista de alunos saem da MESMA funcao. Duas contas escritas separado discordariam no primeiro estado novo, e voce leria a que abrisse primeiro sem saber que a outra diz outra coisa.\n\nVISITANTE E CADASTRADO APARECEM COM UM TRACINHO, nao com zero. Nao existe ficha para eles em lugar nenhum do sistema — e um zero ali seria a tela afirmando que ninguem entrou no site hoje, uma frase que ela nao tem como saber.\n\nSE A PARTE QUE GUARDA OS ALUNOS ESTIVER FORA DO AR, o mapa continua na tela, sem os numeros, com um aviso dizendo isso. Ele descreve as REGRAS, nao as pessoas.\n\nE A PERGUNTA QUE TRAZ VOCE ATE ALI — 'como eu removo um aluno?' — tem a resposta escrita na propria pagina: nao e um botao, e o seletor de situacao, em Ex-aluno.\n\nFATIA 3 DE 5. Faltam: cadastrar alguem a mao, e o aviso pelo sino quando a situacao de alguem muda.",
  autoridade: "github",
  evidencia: "PR #507. Vermelho->verde MEDIDO: sem a mudanca o arquivo de teste nem importa ('from apps.core.views import FAIXAS_DA_JORNADA' -> ImportError). Com ela, 254 passed na celula admin (pytest contra postgres 17 local), black --check limpo, e ci/ci.py --apenas muralhas PASS nos 8 portoes (cerca-de-celula: 1 celula tocada: admin). 11 guardas novos, entre eles test_a_jornada_e_a_lista_dizem_o_mesmo_numero, que abre as DUAS telas na mesma escola e compara os quatro numeros.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null
});})();
