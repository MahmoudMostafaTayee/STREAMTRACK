# run_reconfig_experiment.ps1
# PowerShell script for Esper IOT Example - Reconfigurable Camera Topology Experiment (Scene 2)

Write-Host "Cleaning up port 9999..." -ForegroundColor Cyan
Get-NetTCPConnection -LocalPort 9999 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

$MainClass = "com.espertech.esper.example.IOT.IotMain"
$FeaturesDir = ".\Datasets\EmbedFeature"
$Cameras = "0001,0002,0011,0017,0019,0021,0025,0027,0030"
$CameraGroups = "2,17;1,11;19,27;21,25,30"
$OutputDir = "./output/reconfig_experiment"

$Args = "--scene 2 --features_dir $FeaturesDir --camera '$Cameras' --camera_groups '$CameraGroups' --turbo --output_dir $OutputDir --reconfig"

Write-Host "Starting Maven for Reconfig Experiment..." -ForegroundColor Green
mvn exec:java -Dexec.mainClass="$MainClass" "-Dexec.args=$Args" -Dcheckstyle.skip=true
