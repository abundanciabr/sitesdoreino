# Regressão da sala de aulas em 01/10/2026

A sidebar, os controles de progresso, volume, velocidade, modo cinema e navegação estavam publicados e aprovados na célula `cursos`, commit `1234d722c7fa184fff5c4bf1fe93894d7cc719f5`, às 19:54:42 UTC. A prova dessa versão passou com 869 testes.

A aplicação unificada passou a atender o site posteriormente. Sua versão ativa `1b61f082a40444672317a141ae03cba13d1fc81c`, aprovada às 20:33:49 UTC, foi construída da `main`. As três melhorias finais da sala ainda estavam apenas nas branches publicadas de cursos e não pertenciam à `main`. A aplicação unificada materializa os módulos a partir de `services/<modulo>` do commit escolhido; por isso incorporou a sala antiga, mesmo com o journal legado de cursos ainda indicando a versão nova.

Não houve reversão automática por falha da prova de cursos. A regressão ocorreu na substituição da topologia pelo código principal sem os commits da sala. Foram afetados a sidebar, os novos controles e a correção da faixa preta.

A integração à `main` havia ficado pendente após uma rejeição da revisão automática ao push direto. Publicar a branch corrigiu o site naquele momento, mas não colocou a mudança na fonte usada por futuras publicações da aplicação principal.

Recuperação preparada: integrar à base da aplicação ativa os commits `4761ed6a57c4ef6f20db8a746cca9efd03ed03e1`, `4db51b5cd6dab9bed64b305dfc9b35919f1169f5` e `1234d722c7fa184fff5c4bf1fe93894d7cc719f5`, sem remover as mudanças da unificação. Publicar como `aplicacao` pelo publicador existente, com backup e recuperação automática de código. A prevenção desta causa exige também incorporar essa entrega à `main`; uma publicação isolada de branch não resolve essa pendência.

O vídeo original da Aula 3 (`4lF0RQ_XfMc`) respondeu e reproduziu no curso real durante o diagnóstico: tempo 145 segundos, duração 1230 segundos e `readyState=4`. Não foi necessário substituir o vídeo nem concluir a aula na conta do aluno.
