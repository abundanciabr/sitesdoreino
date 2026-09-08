---
gatilho: "A tela do curso não mostra nenhum Boss"
licao: "O mapa já desenha a marcação e_boss, mas o conteúdo existente precisa ter exatamente um desafio escolhido por módulo. A escolha deve ser aplicada por comando idempotente, com falha sem gravação quando algum título não existir."
---

# Boss do curso precisa de marcação real

O rótulo Boss não pode ser inventado pela posição da aula. Ele é uma marcação
estrutural de `Aula.e_boss`. Para preencher uma base existente, o comando deve
casar curso, módulo e título exato, conferir todos os módulos antes de gravar e
ser seguro para repetir.
