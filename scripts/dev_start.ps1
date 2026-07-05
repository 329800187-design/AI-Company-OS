# AI Company OS — 本地开发启动脚本
# 用法: powershell -ExecutionPolicy Bypass -File scripts/dev_start.ps1
#       或在 PowerShell 中: .\scripts\dev_start.ps1

param(
    [int]$Port = 8000,
    [switch]$NoSmokeCheck
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host ""
Write-Host "  AI Company OS — 本地开发启动" -ForegroundColor Cyan
Write-Host "  ================================" -ForegroundColor DarkGray
Write-Host ""

# ── 1. 检查端口 ──
$existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($existing) {
    $proc = Get-Process -Id $existing.OwningProcess -ErrorAction SilentlyContinue
    $procName = if ($proc) { $proc.ProcessName } else { "unknown" }
    Write-Host "  [WARN] 端口 $Port 已被占用 (PID: $($existing.OwningProcess), 进程: $procName)" -ForegroundColor Yellow
    Write-Host "  如果这是旧的 AI Company OS 实例，可以先关闭它。" -ForegroundColor DarkGray
    Write-Host ""

    $continue = Read-Host "  是否继续启动？(y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        Write-Host "  已取消。" -ForegroundColor Red
        exit 0
    }
}

# ── 2. 检查 Python 环境 ──
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "  [ERROR] 未找到 python，请先安装 Python 3.10+" -ForegroundColor Red
    exit 1
}

$pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "  Python: $pyVersion" -ForegroundColor DarkGray

# ── 3. 启动后端 ──
Write-Host "  启动后端 (uvicorn, port $Port)..." -ForegroundColor Cyan

$env:PYTHONPATH = "$projectRoot;$env:PYTHONPATH"

$backendProc = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", "$Port" `
    -WorkingDirectory $projectRoot `
    -PassThru `
    -WindowStyle Minimized

Write-Host "  后端 PID: $($backendProc.Id)" -ForegroundColor DarkGray

# ── 4. 等待健康检查 ──
$healthUrl = "http://127.0.0.1:$Port/health"
$maxWait = 30
$waited = 0

Write-Host "  等待后端就绪..." -ForegroundColor Cyan

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 1
    $waited++

    try {
        $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 2 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $data = $response.Content | ConvertFrom-Json
            if ($data.status -eq "ok") {
                Write-Host ""
                Write-Host "  [OK] 后端已就绪 (v$($data.version))" -ForegroundColor Green
                break
            }
        }
    }
    catch {
        # 继续等待
    }

    Write-Host "  等待中... ($waited/$maxWait)" -ForegroundColor DarkGray
}

if ($waited -ge $maxWait) {
    Write-Host ""
    Write-Host "  [ERROR] 后端启动超时 ($maxWait 秒)" -ForegroundColor Red
    Write-Host "  请检查终端输出或日志。" -ForegroundColor DarkGray
    Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

# ── 5. 可选：运行 Smoke Check ──
if (-not $NoSmokeCheck) {
    $smokeScript = Join-Path $projectRoot "scripts\backend_smoke_check.py"
    if (Test-Path $smokeScript) {
        Write-Host ""
        Write-Host "  运行 Smoke Check..." -ForegroundColor Cyan
        python $smokeScript --port $Port
    }
}

# ── 6. 打印访问地址 ──
Write-Host ""
Write-Host "  ── 访问地址 ──" -ForegroundColor Cyan
Write-Host "  新版界面:  http://127.0.0.1:$Port/app" -ForegroundColor White
Write-Host "  经典界面:  http://127.0.0.1:$Port/ui" -ForegroundColor DarkGray
Write-Host "  API 文档:  http://127.0.0.1:$Port/docs" -ForegroundColor DarkGray
Write-Host "  健康检查:  $healthUrl" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  按 Ctrl+C 停止后端。" -ForegroundColor DarkGray
Write-Host ""

# ── 7. 保持运行，监控后端进程 ──
try {
    while (-not $backendProc.HasExited) {
        Start-Sleep -Seconds 2
    }
    Write-Host "  后端进程已退出。" -ForegroundColor Yellow
}
catch {
    Write-Host ""
    Write-Host "  正在停止后端..." -ForegroundColor Cyan
    Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    Write-Host "  已停止。" -ForegroundColor Green
}
