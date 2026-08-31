(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-091-a-pagina-no-ar-nao-tinha-mudado",
  tipo: "incidente",
  quando: "2026-08-31",
  titulo: "Eu quase te disse 'esta corrigido' com a pagina ainda dizendo o contrario",
  detalhe: "PRECISO TE CONTAR UM ERRO MEU, E COMO ELE FOI PEGO.\n\nDepois de entregar os cinco passos do reembolso, fui abrir a pagina publica /docs/como-funciona-a-entrada para conferir com os proprios olhos. Ela ainda dizia 'voce devolveu o dinheiro e continua entrando' — a frase exata que voce mandou corrigir.\n\nE tudo estava VERDE. O deploy tinha terminado com sucesso, todos os testes passaram, todos os portoes aprovaram. Se eu tivesse confiado no verde e fechado o relatorio, voce ia abrir a pagina amanha e encontrar a mesma frase errada de hoje.\n\nPOR QUE ACONTECEU: hoje mesmo, mais cedo, o projeto mudou de onde as paginas de /docs/ vem. Antes vinham dos arquivos; agora vem do BANCO DE DADOS, para que VOCE possa edita-las por uma tela sem depender de robo. Os arquivos viraram apenas a SEMENTE — eles plantam o documento uma vez, na primeira vez, e nunca mais mexem no que ja esta plantado. Isso e de proposito, e e a coisa certa: se a semeadura sobrescrevesse, toda atualizacao da plataforma apagaria os textos que voce escreveu.\n\nO efeito colateral e que eu corrigi a receita e o bolo ja estava assado. Nenhum teste avisaria, porque teste roda em banco vazio, onde nao ha bolo nenhum.\n\nISSO JA TINHA ACONTECIDO UMA VEZ, com voce, em 30 de agosto: o travessao que sobreviveu no forum depois de eu declarar tudo limpo. Voce achou olhando o site. A licao estava escrita, o remedio estava escrito, e ainda assim eu quase repeti — a diferenca desta vez foi so eu ter ido conferir no ar em vez de acreditar no verde.\n\nO CONSERTO ja esta feito: uma correcao que alcanca o texto dentro do banco. Ela e cuidadosa de duas formas: so troca se o texto antigo estiver LA EXATAMENTE como era (se voce ja tiver reescrito aquele trecho pela sua tela, ela nao encosta), e troca so aquele pedaco, nunca o documento inteiro — entao qualquer outra coisa que voce tenha editado no mesmo documento continua de pe.\n\nE o teste do conserto teve que FABRICAR o estado do seu servidor a mao, com o texto de ontem dentro dele. Sem isso, ele passaria verde sem ter feito nada — que e exatamente o buraco por onde o problema entrou.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/766 — services/admin/apps/core/migrations/0005_o_reembolso_no_texto_que_ja_esta_no_banco.py e o guarda services/admin/tests/test_reembolso_no_banco.py. Medido nesta sessao, e e o ponto do registro: com o deploy-celula do PR 764 ja em 'success' (conferido por gh run view --json), 'curl https://meshcraft.top/docs/como-funciona-a-entrada' devolvia '<strong>Reembolsado</strong>: voce devolveu o dinheiro e <strong>continua entrando</strong>'. Causa lida no codigo: services/admin/apps/core/documentos.py::importar_da_pasta e get_or_create e roda so na migracao 0003. Molde do conserto: services/forum/apps/forum/migrations/0003, a mesma licao paga em 30/08 com o travessao. Suite da admin 521/521; prova por mutacao com a sabotagem conferida antes: transformar a troca em no-op = 2 vermelhos.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
