$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path

function Require-Text([string]$Path, [string]$Pattern) {
    $content = Get-Content -LiteralPath $Path -Raw
    if ($content -notmatch $Pattern) { throw "Missing contract '$Pattern' in $Path" }
}

$envFile = Join-Path $root 'deploy\CAPO\CAPO.env.example'
$smoke = Join-Path $root 'deploy\native\scripts\smoke-test.sh'
$rollback = Join-Path $root 'deploy\native\scripts\rollback.sh'
$update = Join-Path $root 'deploy\native\scripts\update.sh'
$quickstart = Join-Path $root 'deploy/docker/compose/quickstart.yml'
$units = @(
    'omertaos-install.service', 'omertaos-runtime.service', 'omertaos-control.service',
    'omertaos-gateway.service', 'omertaos-console.service'
) | ForEach-Object { Join-Path $root "deploy\CAPO\systemd\$_" }

@('OMERTAOS_ROOT=', 'CAPO_POSTGRES_ROLE=', 'CAPO_MONGO_ENABLED=false',
  'CAPO_QDRANT_ENABLED=false', 'CAPO_MINIO_ENABLED=false') |
    ForEach-Object { Require-Text $envFile ([regex]::Escape($_)) }

@('127\.0\.0\.1:8000/health', '127\.0\.0\.1:8080/health',
  '127\.0\.0\.1:3000/', '--mode native\|quickstart', 'systemctl is-active') |
    ForEach-Object { Require-Text $smoke $_ }

@('/opt/omertaos/releases', '/opt/omertaos/current', '/opt/omertaos/previous',
  'sha256sum --check', 'no database downgrade was attempted') |
    ForEach-Object { Require-Text $rollback $_ }

@('--backup PATH', 'verified external backup', 'release\.manifest\.sha256',
  'migrate-database\.sh', 'smoke-test\.sh', 'flock') |
    ForEach-Object { Require-Text $update $_ }

@('OMERTA_CONSOLE_HOST_PORT', 'OMERTA_GATEWAY_HOST_PORT', 'OMERTA_CONTROL_HOST_PORT',
  'OMERTA_RUNTIME_HOST_PORT', 'OMERTA_DOCKER_NETWORK') |
    ForEach-Object { Require-Text $quickstart $_ }

foreach ($unit in $units) {
    Require-Text $unit 'NoNewPrivileges=true'
    Require-Text $unit 'PrivateTmp=true'
}

foreach ($unit in $units | Where-Object { $_ -notmatch 'install\.service$' }) {
    Require-Text $unit 'User=omertaos'
    Require-Text $unit 'EnvironmentFile=/etc/omertaos/omertaos\.env'
}

$capoFiles = Get-ChildItem (Join-Path $root 'deploy\CAPO') -File -Recurse
$forbidden = '(?im)^\s*(rm\s+-rf|git\s+(rm|mv)|drop\s+(table|database)|truncate\s+table|mkfs|wipefs)\b'
foreach ($file in $capoFiles) {
    if ((Get-Content -LiteralPath $file.FullName -Raw) -match $forbidden) {
        throw "Forbidden destructive command in $($file.FullName)"
    }
}

Write-Output 'CAPO contract tests passed.'
