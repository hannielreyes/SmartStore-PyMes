# build_and_install.ps1 - Build and validate APK with Flet
# Requirements: flet CLI on PATH, adb in PATH, PowerShell

param(
    [switch]$BuildOnly
)

Set-StrictMode -Version Latest

$buildConfigPath = Join-Path $PSScriptRoot "supabase_build_config.py"
$apkValidatorPath = Join-Path $PSScriptRoot "scripts\validate_apk.py"
$localPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$localFlet = Join-Path $PSScriptRoot ".venv\Scripts\flet.exe"

if (-not (Test-Path $localPython)) {
    throw "No se encontró el entorno Python del proyecto en $localPython. Ejecuta: py -m venv .venv y luego instala requirements.txt."
}
if (-not (Test-Path $localFlet)) {
    throw "No se encontró el CLI de Flet en $localFlet. Instala requirements.txt dentro de .venv."
}
if (-not (Test-Path $apkValidatorPath)) {
    throw "No se encontró el validador de APK requerido en $apkValidatorPath."
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

function Get-AppPackageExclusions([string]$rootPath) {
    # serious_python matches exclusions by exact relative path, not by wildcard.
    $excludedDirectories = @(
        ".git", ".venv", "venv", ".flet", ".pytest_cache", ".vscode", ".idea",
        "__pycache__", "node_modules", "build", "storage", "temp", "scripts",
        "supabase", "tests", "test", ".github", ".devcontainer"
    )
    $excludedFileNames = @(
        ".gitignore", ".gitattributes", ".fletignore", "flet.yaml",
        "pyproject.toml", "requirements.txt", "README.md", "check_supabase.py",
        "camera_test.py", "inspect_fc.py", "webhook.py", "proyecto.py",
        "Untitled.py"
    )
    $exclusions = [System.Collections.Generic.List[string]]::new()
    $pendingDirectories = [System.Collections.Generic.Stack[string]]::new()
    $rootFullPath = [System.IO.Path]::GetFullPath($rootPath).TrimEnd([char[]]@('\', '/')) + [System.IO.Path]::DirectorySeparatorChar
    $pendingDirectories.Push($rootFullPath)

    while ($pendingDirectories.Count -gt 0) {
        $directory = $pendingDirectories.Pop()
        foreach ($entry in [System.IO.Directory]::EnumerateFileSystemEntries($directory)) {
            $relativePath = $entry.Substring($rootFullPath.Length)
            $item = Get-Item -LiteralPath $entry -Force
            if ($item.PSIsContainer) {
                if ($excludedDirectories -contains $item.Name) {
                    $exclusions.Add($relativePath)
                } else {
                    $pendingDirectories.Push($item.FullName)
                }
                continue
            }

            $name = $item.Name
            if (
                $name -match '(?i)^\.env(?:\..*)?$' -or
                $name -ieq "sesion.json" -or
                $name -in $excludedFileNames -or
                $name -match '(?i)\.(?:db|sqlite|sqlite3)(?:-(?:journal|wal|shm))?$' -or
                $name -match '(?i)\.(?:log|sql|md|ps1|tmp|bak|pyc|pyo|key|pem|p8|p12|pfx|jks|keystore)$'
            ) {
                $exclusions.Add($relativePath)
            }
        }
    }

    return @($exclusions | Sort-Object -Unique)
}

function Reset-StaleFlutterExtensionReferences([string]$rootPath) {
    $flutterDirectory = Join-Path $rootPath "build\flutter"
    $pubspecPath = Join-Path $flutterDirectory "pubspec.yaml"
    $baselinePath = "$pubspecPath.orig"
    if (-not (Test-Path -LiteralPath $pubspecPath)) {
        return
    }

    $pubspec = Get-Content -LiteralPath $pubspecPath -Raw
    $hasMissingExtension = $false
    foreach ($match in [regex]::Matches($pubspec, '(?im)^\s*path:\s*["'']?([^"''\r\n]+)')) {
        $extensionPath = $match.Groups[1].Value.Trim()
        if ($extensionPath -match '(?i)[\\/]flutter-packages[\\/]' -and -not (Test-Path -LiteralPath $extensionPath)) {
            $hasMissingExtension = $true
            break
        }
    }
    $hasMissingDependency = $false
    $cachedExtensions = Join-Path $rootPath "build\flutter-packages"
    if (Test-Path -LiteralPath $cachedExtensions) {
        foreach ($extension in (Get-ChildItem -LiteralPath $cachedExtensions -Directory)) {
            $manifestPath = Join-Path $extension.FullName "pubspec.yaml"
            if (-not (Test-Path -LiteralPath $manifestPath)) {
                continue
            }
            $manifest = Get-Content -LiteralPath $manifestPath -Raw
            $nameMatch = [regex]::Match($manifest, '(?im)^name:\s*["'']?([^"''\r\n ]+)')
            if (
                $nameMatch.Success -and
                $pubspec -notmatch "(?im)^\s{2}$([regex]::Escape($nameMatch.Groups[1].Value))\s*:"
            ) {
                $hasMissingDependency = $true
                break
            }
        }
    }
    if (-not $hasMissingExtension -and -not $hasMissingDependency) {
        return
    }

    if ($hasMissingExtension) {
        if (-not (Test-Path -LiteralPath $baselinePath)) {
            throw "Flet tiene una referencia a una extensión Flutter inexistente y no se encontró el manifiesto base $baselinePath."
        }

        $baseline = Get-Content -LiteralPath $baselinePath -Raw
        foreach ($match in [regex]::Matches($baseline, '(?im)^\s*path:\s*["'']?([^"''\r\n]+)')) {
            $extensionPath = $match.Groups[1].Value.Trim()
            if ($extensionPath -match '(?i)[\\/]flutter-packages[\\/]' -and -not (Test-Path -LiteralPath $extensionPath)) {
                throw "El manifiesto base de Flutter también contiene una extensión local inexistente: $extensionPath"
            }
        }

        Copy-Item -LiteralPath $baselinePath -Destination $pubspecPath -Force
    }

    $templateHashPath = Join-Path $rootPath "build\.hash\template-2"
    if (Test-Path -LiteralPath $templateHashPath) {
        Remove-Item -LiteralPath $templateHashPath -Force
    }
    Write-Host "Invalidated Flet's extension template cache so Flutter dependencies are regenerated."
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
    $projectPathPattern = [regex]::Escape([System.IO.Path]::GetFullPath($PSScriptRoot))
    $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine -and
            $_.CommandLine -match $projectPathPattern -and
            $_.CommandLine -match '(?i)gradle|flutter|flet'
        }

    foreach ($proc in $processes) {
        try {
            if ($proc.ProcessId -gt 0) {
                Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
                Write-Host "Detenido proceso de build del proyecto: $($proc.Name) (PID $($proc.ProcessId))"
            }
        } catch {
            Write-Warning "No se pudo detener $($proc.Name) (PID $($proc.ProcessId)): $($_.Exception.Message)"
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
$keyParts = $supabaseKey.Split('.')
if ($supabaseKey -match '(?i)^sb_secret_') {
    throw "SMARTSTORE_SUPABASE_KEY es una clave secreta de servidor y no puede usarse en una APK."
} elseif ($supabaseKey -match '^sb_publishable_[A-Za-z0-9_-]{16,}$') {
    Write-Host "Supabase client key type verified: publishable."
} elseif ($keyParts.Count -eq 3) {
    try {
        $payloadPart = $keyParts[1].Replace('-', '+').Replace('_', '/')
        while (($payloadPart.Length % 4) -ne 0) { $payloadPart += '=' }
        $payloadJson = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payloadPart))
        $payload = $payloadJson | ConvertFrom-Json
        if ($payload.role -eq 'service_role') {
            throw "SMARTSTORE_SUPABASE_KEY es service_role y no puede usarse en una APK."
        }
        if ($payload.role -ne 'anon') {
            throw "No se pudo confirmar que SMARTSTORE_SUPABASE_KEY sea una clave cliente anon."
        }
    } catch {
        throw "No se pudo validar de forma segura el tipo de SMARTSTORE_SUPABASE_KEY; la APK no se construirá."
    }
} else {
    throw "SMARTSTORE_SUPABASE_KEY no tiene un formato cliente anon/public reconocido; la APK no se construirá."
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
    $gradleMemoryOptions = "-Dorg.gradle.jvmargs=-Xmx3G -Dorg.gradle.workers.max=1"
    $env:GRADLE_OPTS = (@($env:GRADLE_OPTS, $gradleMemoryOptions) |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join " "
    Write-Host "Limiting Gradle to a 3 GiB heap and one worker for this build."
    $packageExclusions = @(Get-AppPackageExclusions $PSScriptRoot)
    if (-not $packageExclusions -or $packageExclusions.Count -eq 0) {
        throw "No se pudieron generar exclusiones seguras para el paquete."
    }
    Reset-StaleFlutterExtensionReferences $PSScriptRoot
    Write-Host "Applying $($packageExclusions.Count) exact-path exclusions to the Flet package."
    $buildArguments = @(
        "build", "apk", "--arch", "arm64-v8a", "--yes", "--no-rich-output",
        "--compile-app", "--exclude"
    ) + $packageExclusions
    Write-Host "Building ARM64 APK with Supabase configuration..."
    & $localFlet @buildArguments
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
& $localPython $apkValidatorPath $apk.FullName
if ($LASTEXITCODE -ne 0) {
    throw "La validación de seguridad del APK falló. No se publicará ni instalará."
}
if ($BuildOnly) {
    Write-Host "APK validada. Modo BuildOnly: no se publicó ni se instaló."
    return
}
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
