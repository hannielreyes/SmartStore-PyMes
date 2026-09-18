# build_and_install.ps1 - Build APK with Flet, install on device, and tail adb logs
# Requirements: flet CLI on PATH, adb in PATH, PowerShell

Set-StrictMode -Version Latest

$buildConfigPath = Join-Path $PSScriptRoot "supabase_build_config.py"
$localPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$localFlet = Join-Path $PSScriptRoot ".venv\Scripts\flet.exe"

if (-not (Test-Path $localPython)) {
    throw "No se encontró el entorno Python del proyecto en $localPython. Ejecuta: py -m venv .venv y luego instala requirements.txt."
}
if (-not (Test-Path $localFlet)) {
    throw "No se encontró el CLI de Flet en $localFlet. Instala requirements.txt dentro de .venv."
}

$androidSdkCandidates = @(
    $env:ANDROID_HOME,
    $env:ANDROID_SDK_ROOT,
    "$env:LOCALAPPDATA\Android\Sdk",
    "$env:USERPROFILE\AppData\Local\Android\Sdk",
    "$env:USERPROFILE\Android\Sdk",
    "$env:ProgramFiles\Android\Sdk",
    "$env:ProgramFiles(x86)\Android\Sdk",
    "C:\Android\Sdk",
    "D:\Android\Sdk",
    "E:\Android\Sdk",
    "C:\Users\$env:USERNAME\AppData\Local\Android\Sdk",
    "C:\Users\$env:USERPROFILE\AppData\Local\Android\Sdk"
) | Where-Object { $_ -and $_.Trim() }

$androidSdk = $null
foreach ($candidate in $androidSdkCandidates) {
    if (Test-Path (Join-Path $candidate "platform-tools")) {
        $androidSdk = $candidate
        break
    }
}

if (-not $androidSdk) {
    $androidSdk = $androidSdkCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

if ($androidSdk -and (Test-Path (Join-Path $androidSdk "platform-tools"))) {
    $env:ANDROID_HOME = $androidSdk
    $env:ANDROID_SDK_ROOT = $androidSdk
    $env:Path = "$androidSdk\platform-tools;$androidSdk\cmdline-tools\latest\bin;$env:Path"
} else {
    throw "No se encontró el Android SDK. Instala Android Studio o el SDK de Android y asegúrate de que exista una ruta como: C:\Users\<tu_usuario>\AppData\Local\Android\Sdk . También puedes definir ANDROID_HOME o ANDROID_SDK_ROOT."
}

function Get-EnvValue([string]$name) {
    $line = Get-Content (Join-Path $PSScriptRoot ".env") | Where-Object { $_ -match "^\s*$name\s*=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return (($line -split "=", 2)[1]).Trim().Trim('"').Trim("'")
}

function Upload-SupabaseFile([string]$path, [string]$remotePath, [string]$contentType) {
    $uploadUrl = "$supabaseUrl/storage/v1/object/smartstore-media/$remotePath"
    $headers = @{
        apikey = $supabaseKey
        Authorization = "Bearer $supabaseKey"
        "x-upsert" = "true"
        "Content-Type" = $contentType
    }
    Invoke-RestMethod -Uri $uploadUrl -Method Post -Headers $headers -InFile $path -ContentType $contentType | Out-Null
    return "$supabaseUrl/storage/v1/object/public/smartstore-media/$remotePath"
}

function Stop-StaleAndroidBuildProcesses {
    $patterns = @('GradleDaemon', 'gradle', 'java', 'javaw')
    foreach ($pattern in $patterns) {
        $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -match $pattern -or ($_.CommandLine -and $_.CommandLine -match 'gradle|flutter|android|flet')
            }

        foreach ($proc in $processes) {
            try {
                if ($proc.ProcessId -gt 0) {
                    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
                    Write-Host "Detenido proceso stale: $($proc.Name) (PID $($proc.ProcessId))"
                }
            } catch {
                Write-Warning "No se pudo detener $($proc.Name) (PID $($proc.ProcessId)): $($_.Exception.Message)"
            }
        }
    }

    $lockPaths = @(
        (Join-Path $PSScriptRoot "build\flutter\build"),
        (Join-Path $PSScriptRoot "build\flutter\android\app\build"),
        (Join-Path $PSScriptRoot ".gradle"),
        (Join-Path $PSScriptRoot "build\flutter\build\file_picker\intermediates\lint-cache")
    )

    foreach ($path in $lockPaths) {
        if (Test-Path $path) {
            Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "Limpieza: $path"
        }
    }

    Get-ChildItem -Path $PSScriptRoot -Recurse -Force -Filter *.lock -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue }
}

$envPath = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envPath)) {
    Write-Error "Falta .env. Copia .env.example como .env y pon tu SMARTSTORE_SUPABASE_URL y SMARTSTORE_SUPABASE_KEY."
    exit 1
}

$supabaseUrl = Get-EnvValue "SMARTSTORE_SUPABASE_URL"
$supabaseKey = Get-EnvValue "SMARTSTORE_SUPABASE_KEY"
$updateUrl = Get-EnvValue "SMARTSTORE_UPDATE_URL"
if ([string]::IsNullOrWhiteSpace($supabaseUrl) -or [string]::IsNullOrWhiteSpace($supabaseKey)) {
    Write-Error "Faltan SMARTSTORE_SUPABASE_URL o SMARTSTORE_SUPABASE_KEY en .env."
    exit 1
}
if ([string]::IsNullOrWhiteSpace($updateUrl)) {
    $updateUrl = "$supabaseUrl/storage/v1/object/public/smartstore-media/updates/smartstore-update.json"
}

$version = (Get-Content (Join-Path $PSScriptRoot "pyproject.toml") | Where-Object { $_ -match '^version\s*=\s*"([^"]+)"' } | Select-Object -First 1)
if (-not $version -or $version -notmatch '"([^"]+)"') {
    Write-Error "No se pudo leer la version desde pyproject.toml."
    exit 1
}
$appVersion = $Matches[1]

$buildConfig = @"
SUPABASE_URL = '$($supabaseUrl.Replace("'", "''"))'
SUPABASE_KEY = '$($supabaseKey.Replace("'", "''"))'
UPDATE_URL = '$($updateUrl.Replace("'", "''"))'
APP_VERSION = '$($appVersion.Replace("'", "''"))'
"@
Set-Content -Path (Join-Path $PSScriptRoot "supabase_build_config.py") -Value $buildConfig -Encoding UTF8

try {
    # Limpia el staging anterior para evitar copias recursivas, locks de Gradle y artefactos locales.
    Stop-StaleAndroidBuildProcesses
    Remove-Item (Join-Path $PSScriptRoot "build\python-app") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $PSScriptRoot "build\flutter\build") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $PSScriptRoot "build\python-app\.env") -Force -ErrorAction SilentlyContinue
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    Write-Host "Building ARM64 APK with Supabase configuration..."
    & $localFlet build apk --arch arm64-v8a --yes --no-rich-output
    if ($LASTEXITCODE -ne 0) {
        throw "Flet no pudo construir la APK. Codigo: $LASTEXITCODE"
    }
}
finally {
    Remove-Item $buildConfigPath -Force -ErrorAction SilentlyContinue
}

# Find most recent APK
$apk = Get-ChildItem -Path . -Recurse -Filter *.apk -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $apk) {
    Write-Error "APK not found under project build directories. Check flet build output."
    exit 1
}

Write-Host "Found APK: $($apk.FullName)"
Write-Host "APK lista para instalar en Android y para actualizacion en Supabase."

$remoteApkPath = "updates/SmartStore-$appVersion.apk"
$remoteApkUrl = Upload-SupabaseFile $apk.FullName $remoteApkPath "application/vnd.android.package-archive"
$manifestPath = Join-Path $env:TEMP "smartstore-update.json"
@{
    version = $appVersion
    url = $remoteApkUrl
} | ConvertTo-Json -Compress | ForEach-Object {
    [IO.File]::WriteAllText($manifestPath, $_, (New-Object Text.UTF8Encoding($false)))
}
Upload-SupabaseFile $manifestPath "updates/smartstore-update.json" "application/json" | Out-Null
Remove-Item $manifestPath -Force -ErrorAction SilentlyContinue
Write-Host "Actualizacion publicada: $remoteApkUrl"

$devices = adb devices | Select-String "`tdevice$"
if (-not $devices) {
    Write-Warning "No hay un dispositivo Android conectado. La APK quedó en $($apk.FullName)."
    exit 0
}

Write-Host "Installing APK on device..."
adb install -r "$($apk.FullName)"

Write-Host "Clearing logcat buffer..."
adb logcat -c

Write-Host "Tailing logcat (Ctrl+C to stop). Filtering flet and camera messages..."
adb logcat | Select-String -Pattern "flet|camera|Camera|fc" -SimpleMatch
