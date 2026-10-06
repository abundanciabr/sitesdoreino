"""Conteúdo versionado do plano; o andamento fica no banco, por chave estável."""

PLANO = "praticas-3d-multicursos-v1"


def tarefa(chave, texto, prova, feito=False):
    return {"chave": chave, "texto": texto, "prova": prova, "feito": feito}


FASES = [
    {
        "id": "base", "titulo": "0 · Base confirmada e ponto de partida",
        "entrega": "Aproveitar a sala de aula, a identidade e o portfólio que já funcionam.",
        "depende": "Ponto de partida. As marcações abaixo registram a análise já realizada.",
        "tarefas": [
            tarefa("base-nativa", "Identificar a implementação nativa das práticas e os identificadores atuais das aulas.", "PET, D02, J01 e os três vídeos comerciais identificados; preservar seus endereços e progresso.", True),
            tarefa("base-portfolio", "Conferir o armazenamento de imagens e a separação entre alunos já existentes.", "Portfólio possui imagens no banco, normalização e consulta pelo dono; não é necessário começar um serviço de arquivos do zero.", True),
            tarefa("base-3d", "Conferir o que falta para a interação 3D.", "Há GLB para download; não há visualizador 3D nem receita de personalização integrados às aulas.", True),
            tarefa("base-objetivo", "Registrar o propósito do Desafio e a ordem dos sete dias.", "Simulações sem instalar Blender; práticas 1–3, pitches 4–6, prática final 7; instalação no curso completo.", True),
        ],
    },
    {
        "id": "espada", "titulo": "1 · Uma espada original e um protótipo completo",
        "entrega": "Primeiro item que o aluno consegue explorar e colorir no navegador.",
        "depende": "Usa a base da fase 0. É o próximo trabalho de implementação.",
        "tarefas": [
            tarefa("espada-blender", "Criar a espada original no Blender e preservar o projeto fonte.", "Arquivo .blend e resultado real na tela; nenhuma cópia comercial do Huge Cat ou de item de terceiros."),
            tarefa("espada-partes", "Separar e nomear lâmina, guarda, cabo e joia em português.", "Cada parte tem uma chave estável e material próprio; colorir uma parte não muda as outras."),
            tarefa("espada-catalogo", "Cadastrar a primeira versão da base, miniatura e cores iniciais.", "ID independente da posição do catálogo; GLB versionado, licença/autoria e dimensões de referência registrados."),
            tarefa("espada-biblioteca", "Hospedar no próprio site a biblioteca 3D e os módulos necessários.", "Biblioteca, carregador e controles servidos localmente, com versão e licença preservadas."),
            tarefa("espada-canvas", "Exibir a espada em um quadro 3D estável na sala de aula.", "Carregamento e falha têm resposta legível; o quadro não muda de proporção e não usa iframe."),
            tarefa("espada-cores", "Permitir escolher a parte e mudar suas cores de verdade.", "Paleta e seletor mostram o efeito imediato; há voltar à cor anterior e restaurar a aparência inicial."),
            tarefa("espada-camera", "Permitir girar, aproximar e deslocar a visualização.", "Mouse, toque, pinça e botões acessíveis; reposicionar a vista recupera o item sem apagar suas cores."),
            tarefa("espada-captura", "Gerar a imagem da personalização no navegador.", "PNG mostra as cores escolhidas e o enquadramento, sem controles, setas ou telas pretas."),
        ],
    },
    {
        "id": "salvar", "titulo": "2 · Salvar, fechar e recuperar o projeto do aluno",
        "entrega": "Meu projeto salvo no site, com imagem e estado editável.",
        "depende": "Usa o item e os controles da fase 1. A modelagem dos dados pode começar em paralelo à criação da espada.",
        "tarefas": [
            tarefa("salvar-acesso", "Ligar o projeto à identidade e ao acesso ao curso já usados na plataforma.", "Aluno do Desafio consegue salvar sem precisar comprar o curso completo; conferir a compatibilidade com a categoria exigida pelo portfólio atual."),
            tarefa("salvar-receita", "Guardar a receita com base e versão, partes, cores, vista e etapa da atividade.", "Estado editável permanece no servidor, ligado ao aluno e ao site; IDs e posições da aula ficam separados."),
            tarefa("salvar-imagem", "Guardar a imagem final aproveitando o serviço de imagens existente.", "Imagem e receita apontam para o mesmo projeto; identificação de base preparada e personalização do aluno."),
            tarefa("salvar-resposta", "Mostrar Salvando, Salvo e Tentar novamente sem perder o trabalho.", "Falha de rede não se apresenta como sucesso; nova tentativa atualiza o mesmo projeto e não cria cópias involuntárias."),
            tarefa("salvar-concorrencia", "Tratar gravações repetidas e edições em duas abas.", "Uma atualização atrasada não substitui silenciosamente uma versão mais recente; salvar um projeto não altera outro."),
            tarefa("salvar-reabrir", "Fechar a página e reabrir o mesmo item personalizado.", "Cores, base, etapa e enquadramento recuperados; conferir também em outra sessão ou dispositivo do próprio aluno."),
            tarefa("salvar-privacidade", "Conferir o acesso privado com contas diferentes.", "Outro aluno ou visitante não lê nem modifica receita ou imagem privada; dono vem da sessão, não de um ID enviado pelo navegador."),
            tarefa("salvar-glb", "Oferecer download do GLB personalizado a partir da base confiável.", "Abrir o arquivo e conferir materiais e cores; o download não é anunciado como arquivo .blend ou publicação no Roblox."),
        ],
    },
    {
        "id": "motor", "titulo": "3 · Transformar o protótipo em ferramenta para vários cursos",
        "entrega": "Um motor, um catálogo e configurações de atividades reutilizáveis.",
        "depende": "Apoia-se no caminho completo das fases 1–2. Concluir antes de multiplicar cópias do simulador.",
        "tarefas": [
            tarefa("motor-componente", "Extrair visualizador, cores, câmera, exportação e recuperação para um componente único.", "Nenhum código da espada, do Huge Cat ou do Desafio controla o funcionamento geral do motor."),
            tarefa("motor-atividade", "Criar configuração de atividade vinculada a curso e aula por ID estável.", "Objetivo, catálogo permitido, partes, controles, etapas e textos vêm da atividade; ordem continua editável nos controles atuais."),
            tarefa("motor-projeto", "Separar projeto do aluno, tentativa de atividade e conclusão da aula.", "Usar o mesmo item em outra aula não duplica ou zera o trabalho; não conclui uma aula apenas por abrir o 3D."),
            tarefa("motor-gestao", "Permitir à equipe escolher modelos e preparar atividades na administração existente.", "Equipe configura uma segunda atividade sem copiar HTML ou JavaScript; prévia não publica alterações em outras aulas."),
            tarefa("motor-versoes", "Manter as versões de bases já usadas por projetos salvos.", "Atualizar um modelo do catálogo não muda as cores, partes ou geometria de projetos antigos sem correspondência definida."),
            tarefa("motor-meus-itens", "Adicionar Meus itens à área do aluno com reabertura na aula.", "Miniatura, título e última gravação; coleção lógica no site, sem depender de uma pasta física no computador."),
            tarefa("motor-multicurso", "Aplicar a mesma ferramenta a uma segunda atividade de outro curso.", "Acesso respeita cada matrícula; reutilização ou continuação de um projeto é explícita e não mistura os trabalhos."),
            tarefa("motor-legado", "Conferir aulas e práticas atuais após a inclusão do motor.", "Navegação, comentários, conclusão, downloads e progresso existentes continuam funcionando."),
        ],
    },
    {
        "id": "dia1", "titulo": "4 · Publicar a primeira vitória no Dia 1 do Desafio",
        "entrega": "Escolher → personalizar → explorar → salvar → reconhecer o próprio resultado.",
        "depende": "Usa as fases 1–3. Primeiro piloto com espada; seleção pública amplia quando houver outros itens realmente funcionais.",
        "tarefas": [
            tarefa("dia1-objetivo", "Reescrever a abertura para explicar o objetivo imediato e a base preparada.", "Aluno sabe o que fará nesta página e o que levará ao final; nenhum passo pede instalação ou abertura do Blender."),
            tarefa("dia1-escolha", "Apresentar uma escolha de item sem mostrar opções indisponíveis como prontas.", "Espada como primeiro piloto; depois espada, pet original e boné, todos com personalização e salvamento completos."),
            tarefa("dia1-guia", "Guiar uma primeira mudança e oferecer escolhas livres em seguida.", "Indicação grande no alvo, instrução Clique… ou Toque…; retorno descreve a parte e a cor alteradas, sem predeterminar o resultado."),
            tarefa("dia1-explorar", "Ensinar giro e zoom com uma demonstração curta e um botão para recuperar a vista.", "Aluno entende a diferença entre mudar a cor e apenas olhar o item de outro lado."),
            tarefa("dia1-final", "Mostrar o resultado do próprio aluno no mesmo quadro e confirmar sua gravação.", "Minha espada personalizada, botão baixar imagem e reabrir; sem recarregar a página ou deslocar a tela automaticamente."),
            tarefa("dia1-livia", "Preparar falas, telas e guia sincronizado de gravação para a Lívia.", "Demonstração real em português a 1920 × 1200; texto legível e tempo alinhado às ações; voz real somente quando fornecida."),
            tarefa("dia1-promessa", "Ajustar a promessa do Dia 1 e a ponte para o curso completo.", "Personalização guiada não é modelo criado do zero, item vendável, aprovação UGC ou renda; relatos profissionais usam provas reais fornecidas."),
            tarefa("dia1-integrar", "Atualizar a aula PET dentro do curso, preservando endereço e progresso.", "Visual nativo das aulas; sem página de produção, karaokê da professora ou instruções de bastidor no conteúdo do aluno."),
            tarefa("dia1-publicar", "Publicar com o backup e a recuperação existentes e conferir a aula no site.", "URL PET funcionando, cores, controles, salvar/reabrir, vídeo, celular, navegação e captura do resultado conferidos."),
        ],
    },
    {
        "id": "celular", "titulo": "5 · Catálogo inicial e experiência no celular",
        "entrega": "Três escolhas reais, legíveis e utilizáveis também quando o 3D não estiver disponível.",
        "depende": "Amplia o piloto da fase 4, reaproveitando o motor. Ajustes de celular começam desde a fase 1.",
        "tarefas": [
            tarefa("catalogo-pet", "Preparar um pet original com partes e materiais personalizáveis.", "Mesmo fluxo de cores, gravação e recuperação; Huge Cat permanece uma referência de estudo separada de um item original."),
            tarefa("catalogo-bone", "Preparar um boné original com partes e materiais personalizáveis.", "Mesmo contrato de atividade, miniatura e versão; cada opção entrega uma primeira vitória equivalente."),
            tarefa("celular-toque", "Ajustar controles, letras e seleção de cores para telas pequenas.", "Testar em celular real Android e iPhone; o quadro não prende a rolagem da página e os botões continuam alcançáveis."),
            tarefa("celular-desempenho", "Medir carregamento e fluidez dos modelos reais em aparelhos representativos.", "Registrar dispositivo, tamanho real dos arquivos e comportamento; reduzir geometria/texturas ou resolução do render conforme necessário."),
            tarefa("celular-carregamento", "Antecipar os recursos da próxima etapa sem baixar o catálogo inteiro.", "Carregar e decodificar imagens seguintes quando usadas; liberar recursos 3D ao trocar de modelo ou sair da atividade."),
            tarefa("celular-fallback", "Criar alternativa interativa quando não houver WebGL compatível.", "Imagens em camadas e vistas preparadas permitem escolher cores, salvar e reabrir a mesma receita; indicar quando giro ou GLB não estiverem disponíveis."),
            tarefa("celular-acessibilidade", "Oferecer nomes de cor, foco visível, teclado e respostas textuais.", "A compreensão não depende só da cor, da seta, de arrastar ou da voz; instruções completas continuam disponíveis na tela."),
        ],
    },
    {
        "id": "jornada", "titulo": "6 · Expandir para as demais aulas do Desafio",
        "entrega": "Um projeto contínuo nos Dias 1–3 e 7, presente também nos três pitches.",
        "depende": "Usa o motor e as opções publicadas. Cada atividade continua a escolha do aluno.",
        "tarefas": [
            tarefa("jornada-dia2", "Criar a vitória do Dia 2 com uma alteração simples na forma do item escolhido.", "Controle visual de largura/proporção ou montagem preparada; forma e partes acompanham a alteração; salvar e explicar o que mudou."),
            tarefa("jornada-dia3", "Criar a conferência de um pedido didático no Dia 3.", "Pedido curto, marcado como fictício, orienta uma decisão e uma correção; não usar aprovação simulada como aprovação real do Roblox."),
            tarefa("jornada-arvore", "Manter a aula J01 da árvore como conteúdo complementar com seu endereço.", "Criar ou vincular o novo Dia 3 sem apagar a árvore ou transformar seu progresso em progresso de outra atividade."),
            tarefa("jornada-pitch4", "Retomar o item salvo na abertura do pitch do Dia 4.", "Relacionar escolhas ao trabalho por encomenda e a um exemplo profissional real; vídeo antigo editado pelo mantenedor."),
            tarefa("jornada-pitch5", "Retomar uma ação compreendida no pitch do Dia 5.", "Mostrar como a orientação ajuda a aprender e onde o curso completo ensina instalação e trabalho no Blender."),
            tarefa("jornada-pitch6", "Ligar o projeto guiado ao método e à oferta atual no Dia 6.", "Benefícios correspondem ao curso; preço, garantia, bônus e condições vêm da oferta existente, sem inventar prazo ou resultado financeiro."),
            tarefa("jornada-dia7", "Criar a entrega final e a apresentação do item no Dia 7.", "Aluno escolhe nome e enquadramento, salva imagem e revê suas escolhas; resultado continua acessível sem comprar o curso completo."),
            tarefa("jornada-checkin", "Registrar o avanço das atividades e oferecer compartilhamento opcional.", "Print ou comentário não é necessário para conservar o trabalho; publicar imagem ou link depende de uma escolha explícita do aluno."),
            tarefa("jornada-roteiros", "Revisar os sete roteiros e seus trechos de demonstração.", "Práticas prometem o que a página entrega; contexto permanente; caminho de renda corresponde ao curso; UGC só onde for pertinente e com documentação atual."),
        ],
    },
    {
        "id": "calendario", "titulo": "7 · Jornada individual de sete dias e continuidade comercial",
        "entrega": "Cada aluno começa no primeiro acesso autorizado e conserva seus trabalhos.",
        "depende": "Usa a sequência pronta da fase 6. Intervalos propostos de 24 horas, com início persistido por aluno e curso.",
        "tarefas": [
            tarefa("calendario-inicio", "Persistir o início no primeiro acesso autorizado ao Desafio.", "Atualizar a página, trocar de dispositivo ou abrir uma página de produção não reinicia a jornada."),
            tarefa("calendario-dias", "Associar aulas aos dias sem amarrar o dia à posição na lista.", "Dia 1 imediato; Dias 2–7 em +24, +48, +72, +96, +120 e +144 horas; equipe pode mudar ordem pelos controles existentes."),
            tarefa("calendario-acesso", "Aplicar a programação na navegação e nos endereços diretos.", "Data da próxima aula é clara; conclusão e liberação por tempo são estados distintos; demais cursos não recebem esse calendário."),
            tarefa("calendario-legado", "Preservar acessos e progressos dos participantes atuais.", "Histórico sem data inicial não recebe uma data inventada; aulas já acessíveis ou concluídas não são bloqueadas pela mudança."),
            tarefa("calendario-oferta", "Conferir a continuação para a oferta e o checkout já existentes.", "Compra não apaga o Desafio; nenhum prazo individual de compra, mudança de preço ou envio de mensagem é acrescentado por este plano."),
        ],
    },
    {
        "id": "acompanhar", "titulo": "8 · Acompanhar a aprendizagem e ampliar para outros cursos",
        "entrega": "Ver onde os alunos conseguem agir e onde ainda não entendem o objetivo.",
        "depende": "Começa com o Dia 1 publicado e acompanha as expansões; não depende de uma previsão de vendas.",
        "tarefas": [
            tarefa("acompanhar-eventos", "Registrar início, escolha, primeira mudança, gravação, recuperação e conclusão da prática.", "Eventos próprios do site, sem cores/receitas privadas em ferramentas externas; diferenciar retomar de começar novamente."),
            tarefa("acompanhar-diagnostico", "Comparar alunos que começam, personalizam, salvam e voltam.", "Indicadores por atividade e etapa mostram abandono e falhas; ver mais tempo na página não é tratado como aprendizado."),
            tarefa("acompanhar-compreensao", "Observar se iniciantes entendem a tarefa e a mudança que fizeram.", "Perguntas curtas: O que você vai fazer? e O que você mudou?; registrar dificuldades para corrigir instruções."),
            tarefa("acompanhar-curso", "Relacionar a jornada ao acesso à oferta e às matrículas reais.", "Medição de conversão com a infraestrutura existente; separar personalização, intenção e compra, sem atribuir causalidade não demonstrada."),
            tarefa("acompanhar-documentar", "Registrar no próprio plano o que foi publicado e a evidência de cada entrega.", "Checklist atualizado com URLs e resultados reais; pendências não viram concluídas por haver apenas um desenho ou roteiro."),
            tarefa("acompanhar-reusar", "Publicar uma segunda aplicação em outro curso e documentar sua configuração.", "Novo modelo e atividade reutilizam o motor, a conta e Meus itens; endereços e progressos do segundo curso preservados."),
        ],
    },
]

TAREFAS = {item["chave"]: item for fase in FASES for item in fase["tarefas"]}
