# build_and_install.ps1 - Build APK with Flet, install on device, and tail adb logs
# Requirements: flet CLI on PATH, adb in PATH, PowerShell

Set-StrictMode -Version Latest

$buildConfigPath = Join-Path $PSScriptRoot "supabase_build_config.py"
$localFlet = Join-Path $PSScriptRoot ".venv\Scripts\flet.exe"
$localGit = Join-Path $env:LOCALAPPDATA "Programs\Git\cmd"
$androidSdk = Join-Path $env:USERPROFILE "Android\sdk"

if (-not (Test-Path (Join-Path $androidSdk "platform-tools"))) {
    $androidSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
}
if (Test-Path (Join-Path $androidSdk "platform-tools")) {
    $env:ANDROID_HOME = $androidSdk
    $env:ANDROID_SDK_ROOT = $androidSdk
    $env:Path = "$androidSdk\platform-tools;$androidSdk\cmdline-tools\latest\bin;$env:Path"
} else {
    throw "No se encontró el Android SDK. Ruta esperada: $androidSdk"
}

if (Test-Path (Join-Path $localGit "git.exe")) {
    $env:Path = "$localGit;$env:Path"
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git no está instalado o no está disponible en PATH. Instala Git for Windows y vuelve a ejecutar este script."
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

function Publish-ApkToGitHub([string]$apkPath, [string]$appVersion) {
    $repositoryApk = Join-Path $PSScriptRoot "build\apk\SmartStorePyMEs.apk"
    Copy-Item $apkPath $repositoryApk -Force

    git add -f -- "$repositoryApk"
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo preparar el APK para Git."
    }

    git commit --only -m "Publicar APK $appVersion" -- "$repositoryApk"
    if ($LASTEXITCODE -eq 1) {
        Write-Host "El APK no cambio; no se creo un commit nuevo."
    } elseif ($LASTEXITCODE -ne 0) {
        throw "No se pudo crear el commit del APK."
    }

    git push origin HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo subir el APK al repositorio remoto."
    }
    Write-Host "APK publicado en GitHub: build/apk/SmartStorePyMEs.apk"
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
    # Limpia el staging anterior para evitar copias recursivas y artefactos locales.
    Remove-Item (Join-Path $PSScriptRoot "build\python-app") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $PSScriptRoot "build\flutter\build") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $PSScriptRoot "build\python-app\.env") -Force -ErrorAction SilentlyContinue
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    Write-Host "Building ARM64 APK with Supabase configuration..."
    if (Test-Path $localFlet) {
        & $localFlet build apk --arch arm64-v8a --yes --no-rich-output
    } else {
        flet build apk --arch arm64-v8a --yes --no-rich-output
    }
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
Publish-ApkToGitHub $apk.FullName $appVersion

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
