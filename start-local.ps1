$ErrorActionPreference = "Stop"

$repoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceDir = Split-Path -Parent $repoDir
$toolsDir = Join-Path $workspaceDir ".tools"
$pythonExe = Join-Path $repoDir ".venv\Scripts\python.exe"
$frontendDir = Join-Path $repoDir "frontend"
$runDir = Join-Path $repoDir ".local-run"

$nodeExe = Get-ChildItem -LiteralPath (Join-Path $toolsDir "node") -Recurse -Filter "node.exe" |
    Select-Object -First 1 -ExpandProperty FullName

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python virtual environment not found at $pythonExe"
}
if (-not $nodeExe) {
    throw "Portable Node.js was not found under $toolsDir\node"
}

$viteCli = Join-Path $frontendDir "node_modules\vite\bin\vite.js"
if (-not (Test-Path -LiteralPath $viteCli)) {
    throw "Vite CLI was not found at $viteCli"
}

New-Item -ItemType Directory -Force -Path $runDir | Out-Null

function Test-ListeningPort {
    param([int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connection = $client.ConnectAsync("127.0.0.1", $Port)
        if (-not $connection.Wait(500)) {
            return $false
        }
        return $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Get-DotEnvValue {
    param([string]$Name)

    $envFile = Join-Path $repoDir ".env"
    if (-not (Test-Path -LiteralPath $envFile)) {
        return ""
    }

    $line = Get-Content -LiteralPath $envFile |
        Where-Object { $_ -match "^$([regex]::Escape($Name))=" } |
        Select-Object -First 1
    if (-not $line) {
        return ""
    }

    return ($line.Substring($line.IndexOf("=") + 1)).Trim().Trim('"').Trim("'")
}

function Start-ProjectProcess {
    param(
        [string]$Name,
        [string]$Executable,
        [string[]]$Arguments,
        [string]$WorkingDirectory
    )

    $process = Start-Process `
        -FilePath $Executable `
        -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $runDir "$Name.out.log") `
        -RedirectStandardError (Join-Path $runDir "$Name.err.log") `
        -PassThru

    Set-Content -LiteralPath (Join-Path $runDir "$Name.pid") -Value $process.Id
    Set-Content -LiteralPath (Join-Path $runDir "$Name.process-name") -Value $process.ProcessName
    Set-Content -LiteralPath (Join-Path $runDir "$Name.started") -Value $process.StartTime.ToUniversalTime().Ticks
}

if (-not (Test-ListeningPort -Port 8000)) {
    Start-ProjectProcess `
        -Name "backend" `
        -Executable $pythonExe `
        -Arguments @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -WorkingDirectory $repoDir
}

if (-not (Test-ListeningPort -Port 5173)) {
    Start-ProjectProcess `
        -Name "frontend" `
        -Executable $nodeExe `
        -Arguments @("`"$viteCli`"", "--host", "127.0.0.1", "--port", "5173") `
        -WorkingDirectory $frontendDir
}

$backendReady = $false
$frontendReady = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 1
        $backendReady = $health.status -eq "ok"
    } catch {
        $backendReady = $false
    }

    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:5173/" -UseBasicParsing -TimeoutSec 1
        $frontendReady = $response.StatusCode -eq 200
    } catch {
        $frontendReady = $false
    }

    if ($backendReady -and $frontendReady) {
        break
    }
    Start-Sleep -Milliseconds 250
}

if (-not ($backendReady -and $frontendReady)) {
    throw "Local services did not become ready. Check logs in $runDir"
}

$aiBaseUrl = (Get-DotEnvValue -Name "MAUA_AI_BASE_URL").TrimEnd("/")
$aiApiKey = Get-DotEnvValue -Name "MAUA_AI_API_KEY"
$aiModel = Get-DotEnvValue -Name "MAUA_AI_MODEL"
$aiNetworkReady = $false

if ($aiBaseUrl) {
    try {
        $models = Invoke-RestMethod `
            -Uri "$aiBaseUrl/models" `
            -Headers @{ Authorization = "Bearer $aiApiKey" } `
            -TimeoutSec 8
        $aiNetworkReady = [bool]($models.data | Where-Object { $_.id -eq $aiModel })
    } catch {
        $aiNetworkReady = $false
    }
}

Write-Host "cMob AI - SEMOB is ready."
Write-Host "Chat:    http://127.0.0.1:5173"
Write-Host "Backend: http://127.0.0.1:8000"
Write-Host "Docs:    http://127.0.0.1:8000/docs"
if ($aiNetworkReady) {
    Write-Host "Gemma:   accessible from the current network ($aiModel)" -ForegroundColor Green
} else {
    Write-Warning "Gemma is not accessible from the current network. Confirm that this public IP is authorized."
}
Write-Host "Stop:    .\stop-local.cmd"
