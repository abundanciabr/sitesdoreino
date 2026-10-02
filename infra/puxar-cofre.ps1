# Traz para este PC as cópias de segurança da VPS: o cofre fora da VPS.
#
# Copia só o que é novo ou mudou. Traz também as senhas (env/ e .env) para a pasta senhas.
# Dos backups do banco guarda só os últimos 7 dias, como a VPS (escolha do mantenedor em 02/10/2026).
# Uso:  powershell -NoProfile -ExecutionPolicy Bypass -File puxar-cofre.ps1
# A tarefa agendada "Cofre sitesdoreino" roda uma cópia deste arquivo que fica no próprio cofre.
# Guia: infra/COMO-RESTAURAR.md.
param(
  [string]$Cofre = "$env:USERPROFILE\Cofre-sitesdoreino",
  [string]$Vps = "sitesdoreino-vps"
)
$ErrorActionPreference = "Stop"
# Uma copia por vez: a de logon e a diaria podem se encontrar.
$umaPorVez = New-Object System.Threading.Mutex($false, "Local\CofreSitesdoreino")
if (-not $umaPorVez.WaitOne(0)) { Write-Output "Outra copia ja esta rodando."; exit 0 }
$ssh = "$env:WINDIR\System32\OpenSSH\ssh.exe"
$tar = "$env:WINDIR\System32\tar.exe"
$utf8 = New-Object System.Text.UTF8Encoding $false
$relatorio = @("Ultima copia: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') (hora deste PC)", "")
$tudoIgual = $true
# Backup com carimbo de antes deste dia (UTC) nao vem e sai daqui: ficam os ultimos 7 dias.
$limite = [DateTime]::UtcNow.AddDays(-7).ToString("yyyyMMdd")
function Velho($nome) {
  $m = [regex]::Match([System.IO.Path]::GetFileName($nome), '^(?:.*-)?(\d{8})-\d{6}Z')
  return $m.Success -and ($m.Groups[1].Value -lt $limite)
}

# Pastas que mudam: traz arquivo novo ou de tamanho diferente.
foreach ($pasta in @("backups-de-banco", "admin-midia", "backups-coordenacao")) {
  $local = Join-Path $Cofre $pasta
  New-Item -ItemType Directory -Force $local | Out-Null
  $remota = & $ssh -o BatchMode=yes $Vps "cd /opt/plataforma/$pasta 2>/dev/null && find . -type f ! -name '*.parcial' -printf '%P\t%s\n'"
  if ($LASTEXITCODE -ne 0) { throw "a VPS nao respondeu ao listar $pasta" }
  if ($pasta -eq "backups-de-banco") { $remota = @($remota | Where-Object { $_ -and -not (Velho (($_ -split "`t")[0])) }) }
  $faltam = @()
  $bytes = [int64]0
  foreach ($linha in @($remota)) {
    if (-not $linha) { continue }
    $rel, $tamanho = $linha -split "`t"
    $bytes += [int64]$tamanho
    $arquivo = Join-Path $local ($rel -replace '/', '\')
    if (-not (Test-Path -LiteralPath $arquivo) -or (Get-Item -LiteralPath $arquivo).Length -ne [int64]$tamanho) {
      $faltam += $rel
    }
  }
  if ($faltam.Count -gt 0) {
    $lista = Join-Path $env:TEMP "cofre-$pasta.txt"
    [System.IO.File]::WriteAllText($lista, ($faltam -join "`n") + "`n", $utf8)
    # A leitura passa pelo Docker: a aplicacao grava midia como root com modo 600.
    cmd /c "$ssh -o BatchMode=yes $Vps docker run --rm -i -v /opt/plataforma/${pasta}:/d:ro postgres:17 tar cf - -C /d -T - < $lista | $tar xf - -C $local"
    if ($LASTEXITCODE -ne 0) { throw "a copia de $pasta falhou no meio; rode de novo" }
    Remove-Item $lista
  }
  # Conferencia: todo arquivo da VPS existe aqui com o mesmo tamanho.
  $iguais = 0
  foreach ($linha in @($remota)) {
    if (-not $linha) { continue }
    $rel, $tamanho = $linha -split "`t"
    $arquivo = Join-Path $local ($rel -replace '/', '\')
    if ((Test-Path -LiteralPath $arquivo) -and (Get-Item -LiteralPath $arquivo).Length -eq [int64]$tamanho) { $iguais++ }
  }
  $total = @($remota | Where-Object { $_ }).Count
  if ($iguais -ne $total) { $tudoIgual = $false }
  $relatorio += "{0}: VPS {1} arquivos / {2:N0} bytes; aqui {3} iguais; trazidos agora {4}" -f $pasta, $total, $bytes, $iguais, $faltam.Count
  if ($pasta -eq "backups-de-banco") {
    $velhos = @(Get-ChildItem -LiteralPath $local -File | Where-Object { Velho $_.Name })
    $velhos | Remove-Item -Force
    if ($velhos.Count -gt 0) { $relatorio += "backups-de-banco: sairam daqui {0} arquivos com carimbo de antes de {1}" -f $velhos.Count, $limite }
  }
}

# As senhas (env/ e .env da VPS): com elas uma VPS nova volta com as mesmas chaves.
$senhas = Join-Path $Cofre "senhas"
New-Item -ItemType Directory -Force $senhas | Out-Null
cmd /c "$ssh -o BatchMode=yes $Vps tar cf - -C /opt/plataforma env .env | $tar xf - -C $senhas"
if ($LASTEXITCODE -ne 0) { throw "a copia das senhas falhou; rode de novo" }
$relatorio += "senhas: {0} arquivos (env/ e .env da VPS)" -f @(Get-ChildItem -LiteralPath $senhas -File -Recurse -Force).Count

# admin-dados e admin-dados.new: fotos da fila antiga, que nao mudam mais. Vem uma vez, compactada.
foreach ($pasta in @("admin-dados", "admin-dados.new")) {
  $dados = Join-Path $Cofre $pasta
  New-Item -ItemType Directory -Force $dados | Out-Null
  $pacote = Join-Path $dados "$pasta.tar.gz"
  if (-not (Test-Path $pacote)) {
    cmd /c "$ssh -o BatchMode=yes $Vps nice -n 19 tar czf - -C /opt/plataforma $pasta > $pacote.parcial"
    if ($LASTEXITCODE -ne 0) { Remove-Item -ErrorAction SilentlyContinue "$pacote.parcial"; throw "a copia de $pasta falhou" }
    Move-Item "$pacote.parcial" $pacote
  }
  $relatorio += "{0}: pacote unico de {1:N0} bytes" -f $pasta, (Get-Item $pacote).Length
}

# O guia mais novo, da main que a VPS recebeu.
$guia = Join-Path $Cofre "COMO-RESTAURAR.md"
cmd /c "$ssh -o BatchMode=yes $Vps cat /opt/plataforma/codigo/ferramentas/atual/infra/COMO-RESTAURAR.md > $guia.parcial"
if ($LASTEXITCODE -eq 0 -and (Get-Item "$guia.parcial").Length -gt 0) { Move-Item -Force "$guia.parcial" $guia }
else { Remove-Item -ErrorAction SilentlyContinue "$guia.parcial" }

# O backup mais novo e as contagens dele.
$ultimo = Get-ChildItem (Join-Path $Cofre "backups-de-banco") -Filter "*.contagens.tsv" |
  Sort-Object Name | Select-Object -Last 1
if ($ultimo) {
  $linhas = Get-Content $ultimo.FullName | ForEach-Object { [int64](($_ -split "`t")[2]) } | Measure-Object -Sum
  $relatorio += ""
  $relatorio += "Backup mais novo: {0} ({1} tabelas, {2:N0} linhas no total)" -f ($ultimo.Name -replace '\.contagens\.tsv$', ''), $linhas.Count, $linhas.Sum
}
$relatorio += ""
$relatorio += $(if ($tudoIgual) { "Os dois lados tem os mesmos arquivos com os mesmos tamanhos." } else { "ATENCAO: algum arquivo da VPS nao bateu; rode de novo." })
[System.IO.File]::WriteAllLines((Join-Path $Cofre "ultima-copia.txt"), $relatorio, $utf8)
$relatorio | ForEach-Object { Write-Output $_ }
if (-not $tudoIgual) { exit 1 }
