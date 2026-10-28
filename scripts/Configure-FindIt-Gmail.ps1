[CmdletBinding()]
param([string]$ProjectPath = (Get-Location).Path)
$ErrorActionPreference = 'Stop'
$resolvedProject = (Resolve-Path -LiteralPath $ProjectPath).Path
$envPath = Join-Path $resolvedProject '.env'
if (-not (Test-Path -LiteralPath (Join-Path $resolvedProject 'docker-compose.yml'))) {
    throw 'Open PowerShell in your FindIT folder or provide -ProjectPath.'
}
if (-not (Test-Path -LiteralPath $envPath)) {
    throw 'Create your .env with scripts/dev.ps1 setup first.'
}
Write-Host 'Configure Gmail to send FindIT verification emails.'
Write-Host 'Enable Google 2-Step Verification and create a Gmail App Password first.'
Write-Host 'https://myaccount.google.com/apppasswords'
Write-Host 'Enter the App Password here only. Never paste it into chat.'
$senderEmail = (Read-Host 'Gmail sender email address').Trim().ToLowerInvariant()
if ($senderEmail -notmatch '^[A-Za-z0-9.!#$%&*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$') {
    throw 'Enter a valid Google account email address.'
}
$secureAppPassword = Read-Host 'Google App Password (hidden input, not your normal password)' -AsSecureString
$passwordPointer = [IntPtr]::Zero
try {
    $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureAppPassword)
    $appPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer).Replace(' ', '')
    if ($appPassword -notmatch '^[A-Za-z0-9]{16}$') { throw 'Expected a 16-character Google App Password.' }
    $values = [ordered]@{
        FINDIT_ALLOWED_EMAIL_DOMAINS = '["suh.edu.in","aiml.suh.edu.in"]'
        FINDIT_REQUIRE_EMAIL_VERIFICATION = 'true'
        FINDIT_MAIL_BACKEND = 'smtp'
        FINDIT_MAIL_FROM = ('FindIT <' + $senderEmail + '>')
        FINDIT_SMTP_HOST = 'smtp.gmail.com'
        FINDIT_SMTP_PORT = '587'
        FINDIT_SMTP_SECURITY = 'starttls'
        FINDIT_SMTP_USERNAME = $senderEmail
        FINDIT_SMTP_PASSWORD = $appPassword
    }
    # Preserve unrelated settings, especially the existing database credentials.
    # Single quotes also prevent Docker Compose interpolation of a value.
    $lines = [Collections.Generic.List[string]]::new()
    foreach ($line in [IO.File]::ReadAllLines($envPath)) {
        $replaceLine = $false
        foreach ($key in $values.Keys) {
            if ($line -match ('^\s*' + [regex]::Escape($key) + '\s*=')) { $replaceLine = $true; break }
        }
        if (-not $replaceLine) { $lines.Add($line) }
    }
    foreach ($key in $values.Keys) { $lines.Add($key + "='" + $values[$key] + "'") }
    [IO.File]::WriteAllLines($envPath, $lines.ToArray(), [Text.UTF8Encoding]::new($false))
    Write-Host 'Saved Gmail SMTP settings and both institutional domains to your private .env.'
    Write-Host 'No email has been sent. Run:'
    Write-Host 'docker compose up -d --force-recreate --wait --wait-timeout 180 backend frontend'
    Write-Host 'Then request a NEW verification link at http://localhost:5173/verify-email'
    Write-Host 'Do not include .env when sharing the project ZIP.'
} finally {
    if ($passwordPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer) }
    $appPassword = $null
    $values = $null
    if ($secureAppPassword) { $secureAppPassword.Dispose() }
}
