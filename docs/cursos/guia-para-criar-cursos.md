# Guia para criar cursos aproveitando a sala existente

Este guia ajuda os próximos robôs a criar cursos na Meshcraft aproveitando o que foi construído para o **Desafio Como Ganhar em Dólar com Roblox**. A maior parte do próximo trabalho pode ser cadastro de dados: nome, estrutura, vídeos e acesso dos alunos. A sala, o player, a navegação e os comentários já existem e são compartilhados.

É uma referência de caminhos e problemas conhecidos, sem acrescentar regras, aprovações, workflows ou obrigações. As escolhas do mantenedor e o pedido do novo curso orientam a execução. A leitura do código foi feita em **2 de outubro de 2026**; os caminhos abaixo ajudam a localizar a implementação se ela evoluir.

O guia fica na área administrativa do site, em `/admin/documentos/guia-para-criar-cursos`. Uma cópia de referência para quem trabalha no repositório está em `docs/cursos/guia-para-criar-cursos.md`. Editar o arquivo, por si só, não atualiza o documento do site: o editor de documentos grava no banco.

## Onde começar um novo pedido

Com o nome do curso, os títulos e links das aulas, o tipo de avanço e a definição de quem terá acesso, o robô já consegue montar uma sala equivalente. Público e objetivo ajudam quando houver textos a escrever. Preço e pagamento entram quando o pedido incluir venda; não são necessários para repetir uma sala com vídeos vendida em outro lugar.

No curso de referência, o pedido foi somente uma sala com três aulas do YouTube, sem página de venda, checkout, exercícios ou avaliação da professora. Assim, não houve motivo para inventar materiais, depoimentos, credenciais ou uma estrutura de ensino além dos vídeos enviados.

O robô pode executar o cadastro pelas telas administrativas existentes. Se estiver trabalhando por integração, as mesmas operações estão na API interna. O mantenedor não precisa receber uma lista de tarefas manuais para fazer o trabalho que pediu ao robô.

## O que já está pronto para reaproveitar

| Parte | Comportamento existente | O que varia por curso |
|---|---|---|
| Sala de aulas | Renderização compartilhada em Django | Nome, módulos, aulas e materiais |
| Player do YouTube | Play e pausa próprios, busca no vídeo, volume, mudo, velocidades 1x, 1.5x e 2x, tela cheia e modo cinema | URL e proporção do vídeo |
| Conteúdo do curso | Sidebar à direita em telas largas; abaixo do vídeo até 1099 px; pode fechar e reabrir | Módulos e aulas do curso atual |
| Navegação | Aula anterior e próxima aula; primeira, última e aula fechada têm tratamento próprio | Ordem e disponibilidade das aulas |
| Progresso do curso | Contagem e percentual de aulas concluídas | Progresso de cada aluno |
| Comentários | Privados para autor e admins; públicos para alunos da mesma aula quando um admin os publica | Comentários de cada aula |
| Identificação | Nome real do curso no link superior, com nome da aula ao lado | Nome do curso e título da aula |

Esses recursos não precisam ser copiados para uma nova pasta a cada curso. O template lê os dados da aula atual; uma cópia particular dos componentes criaria duas versões para manter. Uma alteração no componente compartilhado também pode afetar cursos já existentes.

## O curso usado como referência

Nome: **Desafio Como Ganhar em Dólar com Roblox**. Apelido do endereço: `desafio-como-ganhar-em-dolar-com-roblox`. As aulas estão na Parte 1.

| Aula | Número | ID do YouTube | Vídeo recebido |
|---|---|---|---|
| Aula 1 | 01 | `3DqQzY2-uOw` | https://www.youtube.com/watch?v=3DqQzY2-uOw |
| Aula 2 | 02 | `ryJ4utK4G60` | https://www.youtube.com/watch?v=ryJ4utK4G60 |
| Aula 3 | 03 | `4lF0RQ_XfMc` | https://www.youtube.com/watch?v=4lF0RQ_XfMc |

O primeiro link chegou com um ponto e vírgula depois do ID. O endereço acima é a forma limpa usada como referência. São os vídeos deste curso, não vídeos padrão para os próximos.

Mapa do curso: [abrir o curso](https://meshcraft.top/cursos/desafio-como-ganhar-em-dolar-com-roblox/). Exemplo de aula: [abrir a Aula 3](https://meshcraft.top/cursos/desafio-como-ganhar-em-dolar-com-roblox/parte-1/03). O acesso depende da sessão e da matrícula; um redirecionamento para entrar não demonstra, sozinho, que a publicação falhou.

## Caminho pelo cadastro já existente

### Curso e acesso

[Os cursos da escola](https://meshcraft.top/admin/escola/cursos/) oferece criação de curso com nome, apelido, produto e escolha do avanço. O apelido identifica o endereço; o nome identifica o que aparece para o aluno.

O **produto** é o vínculo com a matrícula, mesmo quando não há venda no site. Na criação, a tela permite escolher um produto existente ou criar um com o nome do curso. O curso sem produto não abre a sala para alunos. Ter um produto não significa criar automaticamente uma oferta ou cobrar alguém.

O acesso combina site, curso, produto e matrícula ativa. Em venda externa, a forma de conceder essa matrícula é um assunto separado do player: depende da integração ou do cadastro usado para essa venda. A associação do curso ao produto, por si só, não matricula todos os alunos. Os IDs reais vêm do ambiente, sem copiar o ID do produto do Roblox para o novo curso.

O fluxo de criação faz o produto primeiro e o curso depois. Se só a primeira etapa concluir, o produto já existe e pode ser reaproveitado. Se uma resposta se perder, a listagem mostra o que ficou gravado e evita criar um segundo cadastro com outro apelido por engano.

### Avanço do aluno

`livre` significa que a próxima aula abre quando o aluno conclui a anterior, sem laudo da professora. No curso de referência, o botão **Concluir esta aula** realiza esse avanço. Assistir até o final, arrastar a barra de tempo ou trocar a velocidade não equivale a concluir a aula.

`por_laudo` é o outro modo existente, usado para cursos com entrega e avaliação. A API de criação adota esse modo quando o campo é omitido. Por isso, enviar explicitamente `progressao: "livre"` representa corretamente um pedido de curso como este. Se houver pausas com registros exigidos, elas também participam da conclusão; um curso só de vídeos não precisa ganhar pausas, quiz ou checkpoint sem pedido.

### Módulos e aulas

Um curso novo nasce sem aulas. A tela `/admin/escola/<apelido>/estrutura/` recebe uma lista simples. Para um curso novo com três aulas, o formato existente aceita:

```text
# Módulo 1: Aulas do desafio
01 Aula 1
02 Aula 2
03 Aula 3
```

O nome do módulo é apenas um exemplo para adaptar ao novo pedido. Sem uma linha `## Parte 2` ou `## Parte 3`, as aulas ficam na Parte 1. A ordem da lista define a sequência; o número identifica a aula, independentemente do título.

A tela tem **Prever**, que mostra o resultado sem gravar, e **Importar para o curso**. A importação reconcilia a estrutura inteira, não acrescenta apenas as linhas enviadas. Em curso existente, uma aula omitida pode ser apagada se ainda não tiver rastros de aluno. Essa característica merece atenção quando a intenção é somente acrescentar uma aula: a leitura da estrutura atual ou a prévia já mostram o que sumiria. Exclusão de dados continua dependendo da palavra do mantenedor, como ele já definiu.

A reconciliação preserva vídeos, peças, pausas, quiz e publicação das aulas mantidas. O título de uma aula que já foi preenchido não é substituído pela importação; sua edição acontece no editor da aula. Mudar números para tentar renomear títulos mexe na identidade das aulas e pode gerar perda de conteúdo.

### Vídeos e publicação das aulas

A lista fica em `/admin/escola/<apelido>/aulas/`. O caminho específico para inserir só o vídeo é:

```text
/admin/escola/<apelido>/parte-1/aulas/01/video-do-youtube/
```

Nessa tela, **Salvar e publicar aula** lê a aula existente, troca a URL do vídeo, preserva os demais campos e tenta publicá-la. Ela dispensa preencher o editor completo com informações que o curso não tem. Se salvar funcionar e publicar falhar, a tela distingue os dois resultados; uma aula salva em rascunho ainda não é uma aula disponível para o aluno.

O modelo aceita links HTTPS de `youtu.be/ID`, `youtube.com/watch?v=ID`, `youtube.com/embed/ID` e `youtube.com/shorts/ID`. A sala extrai o ID e monta o iframe. Um ID com pontuação sobrando não passa pela mesma leitura de um ID válido.

Depois de publicada, a aula usa `/cursos/<apelido>/parte-1/01`. O número `01` é preservado com o zero inicial. Quando há vários cursos, esse endereço completo evita a ambiguidade de uma rota antiga que traz apenas o número da aula.

## Caminho equivalente pela API

A implementação está em `services/cursos/apps/core/api.py`; o contrato está em `contracts/cursos.openapi.yaml`. O prefixo público atual é `/cursos/api/cursos/`. As operações recebem `site_id` e usam autenticação já provisionada. O guia não contém tokens nem exemplos com credenciais.

| Operação | Finalidade |
|---|---|
| `listCourses` | Ler os cursos do site antes de criar ou alterar |
| `createCourse` | Criar nome, apelido, progressão e vínculo com produto |
| `putCourse` | Alterar nome, progressão ou produto de um curso existente |
| `putCourseStructure` | Gravar módulos e aulas do curso inteiro |
| `listLessons` e `getLesson` | Ler a estrutura e o conteúdo existente |
| `putLesson` | Gravar conteúdo de uma aula |
| `publishLesson` | Publicar a aula gravada |

Exemplo de corpo de criação, com valores ilustrativos:

```json
{
  "slug": "apelido-do-novo-curso",
  "nome": "Nome do novo curso",
  "progressao": "livre",
  "produto_id": "ID_REAL_DO_PRODUTO"
}
```

Exemplo de estrutura para um curso novo:

```json
{
  "blocos": [
    {
      "letra": "A",
      "parte": 1,
      "nome": "Aulas do curso",
      "aulas": [
        {"numero": "01", "titulo": "Aula 1"},
        {"numero": "02", "titulo": "Aula 2"},
        {"numero": "03", "titulo": "Aula 3"}
      ]
    }
  ]
}
```

`putLesson` tem um corpo de conteúdo completo: enviar apenas `video_url` não corresponde ao schema atual. O caminho econômico para mudar um vídeo é a tela específica ou a leitura por `getLesson` seguida da montagem dos campos de `AulaParaGravarSchema`. Estado, número, bloco e data de publicação não são campos de edição desse corpo. Salvar e publicar são operações distintas na API.

## Onde estão os componentes compartilhados

Os caminhos abaixo são relativos à raiz do projeto, `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923`.

| Procurar | Arquivo ou pasta |
|---|---|
| Página da aula | `services/cursos/apps/core/templates/cursos/aula.html` |
| Marcação e controles do player | `services/cursos/apps/core/templates/cursos/_player_youtube_vsl.html` |
| Enquadramento e estilo do player | `services/cursos/static/cursos/player_youtube_vsl.css` |
| Integração com a API do YouTube | `services/cursos/static/cursos/player_youtube_vsl.js` |
| Sidebar e estados das aulas | `services/cursos/apps/core/templates/cursos/_conteudo_do_curso.html` |
| Layout responsivo da sala | `services/cursos/static/cursos/sala.css` |
| Fechar e reabrir o conteúdo | `services/cursos/static/cursos/sala_aula.js` |
| Vídeo, navegação, progresso exibido e filtro de comentários | `services/cursos/apps/core/views.py` |
| Estado e conclusão das aulas | `services/cursos/apps/cursos/progresso.py` |
| Dados de curso, aula e comentário | `services/cursos/apps/cursos/models.py` |
| Cadastro e edição pelo Admin | `services/admin/apps/core/cursos.py`, `estrutura.py` e `aulas.py` |
| Comentários na sala | `services/cursos/apps/core/templates/cursos/_comentarios.html` |
| Moderação | `services/cursos/apps/core/comentarios_api.py` e `services/admin/apps/core/comentarios_aulas.py` |

Os templates usam rotas nomeadas para os links e para os arquivos estáticos. Esse mecanismo já incorpora os prefixos usados em produção. Uma URL escrita à mão pode funcionar num teste local e quebrar quando o módulo é servido sob `/cursos`.

## O player aprovado e sua evolução

A referência original enviada pelo mantenedor foi a subpasta `C:\Users\davia\paginas\ferramentas\player-gpt\sem-titulo\`, com `index.html`, `player_youtube_vsl.css` e `player_youtube_vsl.js`. A pasta acima dela tinha outra versão. O endereço `http://127.0.0.1:8937/sem-titulo/` servia para teste quando o servidor local estava ligado; sua indisponibilidade não significa que os arquivos deixaram de existir.

A implementação integrada na sala é o ponto de partida mais completo: recebeu os controles adicionais, a sidebar, a navegação, a retirada das legendas e a correção da faixa preta. Copiar novamente o exemplo antigo inteiro perderia essas evoluções. Os vídeos de demonstração do exemplo também não são os vídeos de uma aula nova.

Cada raiz tem `data-vsl-youtube` e `data-video-id`. O JavaScript carrega `https://www.youtube.com/iframe_api` e cria `YT.Player` com host `https://www.youtube-nocookie.com`. A configuração integrada é:

```json
{
  "autoplay": 0,
  "cc_load_policy": 0,
  "controls": 0,
  "disablekb": 1,
  "enablejsapi": 1,
  "fs": 0,
  "iv_load_policy": 3,
  "modestbranding": 1,
  "playsinline": 1,
  "rel": 0
}
```

O tratamento visual do título vem do enquadramento, não apenas dos parâmetros. O iframe é ampliado em 240 px e deslocado 120 px para cima; as bordas ficam fora do quadro. A correção integrada usa `overflow: clip` no quadro:

```css
.vsl-youtube__quadro {
  aspect-ratio: 16 / 9;
  overflow: clip;
  position: relative;
}
.vsl-youtube__quadro > iframe {
  border: 0;
  height: calc(100% + 240px);
  left: 0;
  pointer-events: none;
  position: absolute;
  top: -120px;
  width: 100%;
}
```

Este recorte explica a geometria; o arquivo completo contém os estilos e estados necessários. O formato horizontal usa 16/9. A variante vertical usa 9/16, e a view identifica URLs de Shorts para ativá-la.

Os controles chamam `playVideo`, `pauseVideo`, `seekTo`, volume e velocidade. Os eventos da API sincronizam os ícones e rótulos, inclusive a classe `em-reproducao`. Velocidades indisponíveis para um vídeo ficam desabilitadas. Tela cheia usa o contêiner do vídeo e preserva os controles próprios; modo cinema amplia a apresentação na página, sem ser a mesma coisa que tela cheia.

Após carregar, o iframe recebe `title="Reprodutor de vídeo"` e `tabindex="-1"`. O player impede o menu de contexto e desativa o módulo de legendas quando ele aparece. Isso controla as legendas do player; texto que já faça parte da imagem do vídeo não pode ser retirado por essa configuração.

## Comentários e apresentação da sala

O comentário nasce privado. A leitura do aluno filtra os comentários da aula atual pelo próprio autor ou por `publico=True`. A moderação está em [Comentários das aulas](https://meshcraft.top/admin/escola/comentarios/): admins podem torná-los públicos ou privados, com registro de quem alterou e quando. “Público” aqui significa visível para os alunos com acesso à mesma aula, não uma página aberta na internet.

A privacidade está no servidor e na autenticação da moderação. Remover uma frase do template não muda quem pode ler. O texto do comentário é renderizado com escape; ele não precisa virar HTML livre para aparecer abaixo do vídeo.

O mantenedor pediu uma sala enxuta. A versão ajustada removeu o cartão acima do vídeo com número, “Em produção” e título grande; o título da aula continua na faixa superior e no conteúdo do curso. O link “Mapa das portas” passou a mostrar o nome real do curso. O rótulo visível é “Em andamento”, embora o estado interno ainda seja `em_producao`.

Também foram retirados, para aulas do YouTube, o título “O vídeo da aula” e o link “Abrir o vídeo em outra aba”. Saíram as frases “Terminou? Conclua a aula, e a próxima abre na hora.” e “Seu comentário é privado: só você e os admins podem vê-lo. Os admins podem torná-lo público para os alunos desta aula.” O botão de conclusão e a privacidade continuaram funcionando. O template ainda pode exibir pedido e cliente quando uma aula de outro tipo realmente tiver esses dados.

## Problemas encontrados e atalhos para diagnóstico

| Sinal | O que se encontrou ou o que distinguir | Onde olhar primeiro |
|---|---|---|
| Faixa preta grande abaixo da imagem | O quadro com `overflow: hidden` permitia rolagem interna no iframe ampliado. A correção trocou para `overflow: clip`, mantendo o recorte do título | `player_youtube_vsl.css`; commit `4761ed6a57c4ef6f20db8a746cca9efd03ed03e1` |
| Sidebar e controles voltaram ao desenho antigo | A aplicação unificada usou a versão principal, que ainda não tinha os commits publicados numa branch de cursos | Código ativo da aplicação e histórico da `main` |
| Aula 3 parece não funcionar | O vídeo original reproduziu durante o diagnóstico. Não foi preciso trocar o ID nem concluir a aula para repará-lo | URL gravada, disponibilidade da aula, carregamento da API e erro real do player |
| Próxima aula desabilitada | Pode ser a progressão normal: a anterior ainda não foi concluída; também pode ser a última aula | Estado do aluno e ordem das aulas |
| Curso criado, mas sala não abre | Produto ausente, matrícula incompatível ou nenhuma aula publicada são situações diferentes | Cadastro do curso, matrícula e estado das aulas |
| Título não muda após importar estrutura | A reconciliação preserva um título já preenchido | Editor da aula ou `putLesson` |
| Salvar vídeo deu certo, mas aula não aparece | Gravação e publicação são etapas separadas | Resultado da publicação da aula |
| Teste local passa, mas CSS ou link falha no site | Prefixos e rota de estáticos podem ser diferentes | Rotas nomeadas, `moldura.html` e `config/urls.py` |

A regressão está descrita em `docs/incidentes/2026-10-01-regressao-sala-aulas.md`. As melhorias finais estavam publicadas na célula `cursos`, mas não pertenciam à `main`. Quando a aplicação unificada passou a atender o site, materializou `services/<modulo>` de outro commit e trouxe a sala antiga. O journal legado de cursos ainda apontava para a versão nova, o que confundia a leitura do estado.

Nesse incidente não houve reversão automática causada por falha dos testes da sala. A integração à principal havia ficado pendente após uma rejeição da revisão automática ao push. Publicar a branch resolveu a aparência naquele momento, mas deixou a fonte usada pelas próximas publicações sem a entrega. A recuperação integrou as melhorias à base da aplicação e à principal. O diagnóstico de “voltou” ganha precisão quando distingue substituição por outra versão, cache e recuperação automática após falha.

Houve ainda uma atualização concorrente da principal durante a remoção dos textos. As duas entregas foram integradas, preservando ambas. Um checkout antigo ou uma candidata montada antes dessa integração não representa necessariamente o que o site precisa publicar agora. Comparar os commits e incorporar a entrega à fonte usada pelo site evita repetir essa causa, sem criar outro workflow.

## Cadastro de conteúdo e publicação de código

Criar curso, importar aulas, trocar URLs e publicar aulas são gravações de conteúdo pelas ferramentas existentes. Quando o próximo pedido couber nesses recursos, não é necessário editar templates nem iniciar uma publicação de código para cada vídeo.

Quando houver mudança no funcionamento compartilhado, o publicador existente da VPS atende a aplicação unificada. `infra/publicar.py`, `infra/plataforma.sh` e `infra/publicacao-local.py` mostram o caminho atual. O comando `/opt/plataforma/bin/plataforma estado` ajuda a identificar a versão que realmente atende o site. Os journals ficam em `/opt/plataforma/publicacoes/` e os logs em `/opt/plataforma/publicacoes/logs/`.

O mantenedor já definiu backup antes de publicação e retorno automático do código à última versão aprovada se a prova falhar ou o site cair, sem restauração automática do banco. O mecanismo existente está nos arquivos de publicação e recuperação; o manual não acrescenta outra aprovação ou rotina. Restaurar código não desfaz automaticamente comentários, matrículas ou progresso gravados no banco.

## Evidências já disponíveis e observações úteis

A entrega de simplificação dos textos foi registrada no commit `fb1b51c8873aeaaf54c1ca48edd7136dbc6d60a9`; sua integração à principal foi `5ea0eb927fbeb76dbef857c1bfb70af57683cc96`. Naquela entrega, 103 testes locais selecionados passaram, e a publicação registrou 890 testes do módulo de cursos aprovados. São evidências daquela versão, não uma contagem garantida para versões futuras.

O registro local está em `.tmp/textos-sala-evidencia.json`, com captura em `.tmp/sala-textos-atualizados.png`. Esses arquivos temporários podem deixar de existir. O log da publicação foi `/opt/plataforma/publicacoes/logs/aplicacao-fb1b51c8873a-2782098.log`; o backup de cursos foi `/opt/plataforma/backups-de-banco/cursos_db-20261002-124911Z.dump`. São referências históricas, não o backup de um próximo curso.

Para investigar uma alteração, já existem exemplos em `services/cursos/tests/test_catalogo_de_cursos.py`, `test_estrutura_de_curso.py`, `test_telas_da_sala.py`, `test_progressao_livre.py` e `test_comentarios_aulas.py`. No Admin, `services/admin/tests/test_escola_estrutura.py` e `test_comentarios_aulas.py` ajudam a localizar os comportamentos correspondentes. Usar esses exemplos costuma ser mais econômico que inventar uma segunda implementação ou repetir toda a investigação.

No navegador, sinais úteis de funcionamento são o vídeo correto carregando, play e pausa respondendo, busca e volume funcionando, velocidades refletidas no player, entrada e saída de tela cheia e cinema, troca entre aulas e sidebar passando para baixo em tela pequena. Para comentários, duas contas de alunos distinguem comentário próprio, comentário alheio privado e comentário publicado pelo admin; o filtro do servidor é a evidência de privacidade, não só a aparência da tela.

No teste do curso de referência, o mantenedor autorizou concluir as Aulas 1 e 2 na conta aberta. A autorização dizia respeito àquele teste; não é uma autorização permanente para alterar o progresso de outros alunos. Abrir uma aula disponível também pode marcar seu estado como “Em andamento”. Uma conta de teste evita confundir essa observação com uso real do aluno.

## Ponto de partida para o próximo robô

Um pedido reaproveitável pode trazer: “Crie a sala do curso [nome], com estas aulas e vídeos [lista], avanço [livre ou por avaliação] e acesso [público esperado e forma de matrícula]. Use o guia para localizar os recursos já existentes e adapte ao que foi pedido. Faça o cadastro e entregue o endereço funcionando.”

O ganho principal é começar pelo que muda no novo curso. A infraestrutura desta sala já foi construída: os dados novos podem usar o mesmo player, navegação, sidebar, progresso e comentários sem reconstruir essas partes.
