# Cria as listas ContasAWS e RelatoriosCustos via PnP PowerShell.
# Pre-requisito: Install-Module PnP.PowerShell
# Uso:  ./criar-listas.ps1 -SiteUrl "https://<tenant>.sharepoint.com/sites/<site>"
param(
    [Parameter(Mandatory = $true)][string]$SiteUrl
)

Connect-PnPOnline -Url $SiteUrl -Interactive

# ---------- ContasAWS ----------
New-PnPList -Title "ContasAWS" -Template GenericList -OnQuickLaunch
Add-PnPField -List "ContasAWS" -DisplayName "AccountId"         -InternalName "AccountId"         -Type Text    -AddToDefaultView -Required
Add-PnPField -List "ContasAWS" -DisplayName "RoleArn"          -InternalName "RoleArn"           -Type Text    -AddToDefaultView -Required
Add-PnPField -List "ContasAWS" -DisplayName "ExternalId"       -InternalName "ExternalId"        -Type Text
Add-PnPField -List "ContasAWS" -DisplayName "Dono"             -InternalName "Dono"              -Type User    -AddToDefaultView -Required
Add-PnPField -List "ContasAWS" -DisplayName "LimiteItemUSD"    -InternalName "LimiteItemUSD"     -Type Number  -AddToDefaultView -Required
Add-PnPField -List "ContasAWS" -DisplayName "CrescimentoMaxPct" -InternalName "CrescimentoMaxPct" -Type Number -AddToDefaultView -Required
Add-PnPField -List "ContasAWS" -DisplayName "HorarioEnvio"     -InternalName "HorarioEnvio"      -Type Number
Add-PnPField -List "ContasAWS" -DisplayName "TeamId"           -InternalName "TeamId"            -Type Text
Add-PnPField -List "ContasAWS" -DisplayName "ChannelId"        -InternalName "ChannelId"         -Type Text
Add-PnPField -List "ContasAWS" -DisplayName "Ativo"            -InternalName "Ativo"             -Type Boolean -AddToDefaultView
Set-PnPField -List "ContasAWS" -Identity "Ativo" -Values @{ DefaultValue = "1" }

# ---------- RelatoriosCustos ----------
New-PnPList -Title "RelatoriosCustos" -Template GenericList -OnQuickLaunch
Add-PnPField -List "RelatoriosCustos" -DisplayName "Conta"            -InternalName "Conta"            -Type Text   -AddToDefaultView
Add-PnPField -List "RelatoriosCustos" -DisplayName "AccountId"        -InternalName "AccountId"        -Type Text
Add-PnPField -List "RelatoriosCustos" -DisplayName "DataEnvio"        -InternalName "DataEnvio"        -Type DateTime -AddToDefaultView
Add-PnPField -List "RelatoriosCustos" -DisplayName "TotalUSD"         -InternalName "TotalUSD"         -Type Number -AddToDefaultView
Add-PnPField -List "RelatoriosCustos" -DisplayName "TotalAnteriorUSD" -InternalName "TotalAnteriorUSD" -Type Number
Add-PnPField -List "RelatoriosCustos" -DisplayName "ItensEmAlerta"    -InternalName "ItensEmAlerta"    -Type Number -AddToDefaultView
$status = Add-PnPField -List "RelatoriosCustos" -DisplayName "Status" -InternalName "Status" -Type Choice -AddToDefaultView
Set-PnPField -List "RelatoriosCustos" -Identity "Status" -Values @{ Choices = @("Controlado", "Atencao", "Erro") }
Add-PnPField -List "RelatoriosCustos" -DisplayName "ResumoJson"       -InternalName "ResumoJson"       -Type Note

Write-Host "Listas criadas em $SiteUrl" -ForegroundColor Green
