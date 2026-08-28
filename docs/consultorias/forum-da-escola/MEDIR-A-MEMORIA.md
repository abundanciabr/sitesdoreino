# Medir a memória do servidor — o comando que encerra a dúvida do Discourse

**Por que isto existe:** você leu que o Discourse cabe em pouca memória, e a
leitura não é absurda. Só que ninguém neste projeto **nunca mediu** quanta
memória sobra livre na VPS — sabemos que o total é 2 GB e que já há 24
contêineres rodando, e só. Enquanto o número não existir, "cabe Discourse?" é
opinião, minha e sua. Com o número, vira fato.

O resultado serve para esta decisão e para todas as próximas: é a primeira
medição de fôlego da máquina que este projeto terá.

---

## ONDE COLAR — leia esta parte antes

Este comando é para colar **DENTRO DO SERVIDOR**, não no seu PC.

Como saber onde você está, pelo começo da linha:

| O que aparece na frente da linha | Onde você está |
|---|---|
| `PS C:\>` ou `C:\Users\davia>` | No seu **PC**. ❌ **Não é aqui.** |
| `deploy@srv...` ou `root@srv...` | Já está **DENTRO do servidor**. ✅ É aqui. |

Se ainda não estiver dentro do servidor, entre primeiro (o passo de sempre) e
só então cole o bloco abaixo.

## O que vai acontecer

- O comando **só lê** — não instala, não apaga, não reinicia nada. É seguro.
- Se ele perceber que foi colado na janela errada, ele **para sozinho** e avisa,
  em vez de mostrar número errado.
- A parte que mede os contêineres demora **uns 10 a 20 segundos** e fica
  aparentemente parada nesse tempo. É normal — espere.
- No fim ele imprime um resumo. **Copie tudo o que aparecer, do começo ao fim,
  e me mande.**

## O bloco — copie inteiro, de uma vez

```bash
medir_folego_da_maquina() {
  echo "== MEDIÇÃO DE FÔLEGO DA MÁQUINA =="
  if [ ! -d /opt/plataforma ]; then
    echo "PAROU POR SEGURANÇA: não encontrei a pasta /opt/plataforma."
    echo "Isto quase sempre quer dizer que este bloco foi colado no PC, e não"
    echo "dentro do servidor. Confira o começo da linha: precisa ser deploy@srv"
    echo "ou root@srv. Nenhum número foi medido, nada foi alterado."
    return 1
  fi
  if ! command -v docker >/dev/null 2>&1; then
    echo "PAROU POR SEGURANÇA: o comando docker não existe nesta janela."
    echo "Estou no servidor certo? Nenhum número foi medido."
    return 1
  fi
  if ! docker ps >/dev/null 2>&1; then
    echo "PAROU POR SEGURANÇA: o docker existe mas recusou responder."
    echo "Copie esta mensagem inteira e mande para o robô. Nada foi alterado."
    return 1
  fi
  echo
  echo "-- 1. Memória da máquina (em MB) --"
  free -m
  echo
  echo "-- 2. Quantos contêineres estão rodando --"
  docker ps -q | wc -l
  echo
  echo "-- 3. Quanto cada contêiner está usando (leva uns 15 segundos) --"
  docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}'
  echo
  echo "-- 4. Espaço em disco --"
  df -h / | tail -n 2
  echo
  echo "-- 5. Resumo em uma linha --"
  free -m | awk '/^Mem:/ {printf "Total: %s MB | Em uso: %s MB | Disponível de verdade: %s MB\n", $2, $3, $7}'
  free -m | awk '/^Swap:/ {printf "Swap (memória de emergência em disco): total %s MB, em uso %s MB\n", $2, $3}'
  echo
  echo "== FIM DA MEDIÇÃO — copie tudo acima e mande para o robô =="
}
medir_folego_da_maquina
```

## Como o robô vai ler isso

O número que decide é o **"Disponível de verdade"** da linha 5 (a coluna
`available` do Linux — memória que o sistema consegue entregar a um programa
novo agora, já descontando o que dá para liberar de cache).

Régua honesta, para você acompanhar o raciocínio:

| Disponível de verdade | O que significa para o fórum |
|---|---|
| Menos de 300 MB | Apertado até para uma célula Django nova. Qualquer fórum de prateleira está fora, e vale conversar sobre aumentar a VPS |
| 300 a 700 MB | Cabe confortavelmente uma célula nossa. Discourse continua fora |
| Acima de 700 MB, com swap | Aí sim vale reabrir o Discourse como opção real, com a ressalva da atualização sem acesso ao servidor, que continua valendo |

O item 4 (disco) entra de brinde porque o "mostre seu trabalho" do fórum — aluno
postando print, modelo e vídeo — é a coisa mais capaz de encher disco neste
projeto, e é melhor saber a folga antes de prometer anexos.
