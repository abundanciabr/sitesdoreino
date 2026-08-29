(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-101-agora-voce-pode-cadastrar-um-aluno-a-mao",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "Agora voce pode cadastrar um aluno a mao — sem esperar que a pessoa peca",
  detalhe: "ATE HOJE, TODA FICHA NASCIA DE UM PEDIDO DA PESSOA OU DE UMA COMPRA. Se um aluno seu nao conseguisse usar o formulario do site — errou o e-mail da conta Google, nao achou a pagina, ou simplesmente te chamou no WhatsApp — nao havia nada que voce pudesse fazer. Agora ha.\n\nONDE: em meshcraft.top/admin/escola/alunos/, entre a fila e a lista, tem 'Cadastrar alguem a mao'. Fica FECHADO por padrao, porque e a excecao e nao a rotina — um formulario grande sempre aberto ali empurraria para baixo as duas coisas que voce de fato abre essa tela para fazer.\n\nO QUE ELE PEDE: nome, e-mail (o mesmo da conta Google da pessoa, senao ela nao vai se reconhecer no site), WhatsApp com DDD, e opcionalmente turma e data da compra. Com uma escola so, ele NAO pergunta de qual escola — o sistema descobre sozinho.\n\nCOMO FUNCIONA POR DENTRO: a pessoa entra na fila e e liberada na sequencia. E o mesmo caminho de todo mundo, so que depressa. Nao inventei uma porta nova de virar aluno: duas formas de entrar, com duas regras, discordariam na primeira mudanca de lei.\n\nSE A LIBERACAO FALHAR, NADA SE PERDE: a pessoa fica esperando na fila, ali em cima, com o botao Liberar do lado — e a tela diz isso, com um 'Nao cadastre de novo' escrito com todas as letras. Um 'nao deu certo' generico faria voce tentar outra vez e criar duas fichas para a mesma pessoa.\n\nE SE A PARTE QUE GUARDA OS ALUNOS NAO RESPONDER, a tela diz que o cadastro PODE ter sido feito e manda procurar a pessoa na lista antes de tentar de novo. 'Nao sei' nunca vira 'nao deu certo' aqui.\n\nFATIA 4 DE 5. Falta uma: avisar pelo sino quando a situacao de alguem muda.",
  autoridade: "github",
  evidencia: "PR #508. Vermelho->verde MEDIDO: sem a mudanca o arquivo de teste nem importa ('from apps.core.views import conferir_cadastro' -> ImportError). Com ela, 273 passed na celula admin (pytest contra postgres 17 local), black --check 48 files unchanged, e ci/ci.py --apenas muralhas PASS nos 8 portoes. 18 guardas novos. NENHUMA mudanca de contrato: reusa POST /pre-matriculas e POST /pre-matriculas/{id}/decisao, que ja estavam congeladas. Um guarda de 28/08 (test_com_uma_escola_so_o_codigo_interno_dela_nao_aparece) reprovou a primeira versao do formulario e foi o que motivou a escola ser descoberta pelo servidor em vez de perguntada na tela.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null
});})();
