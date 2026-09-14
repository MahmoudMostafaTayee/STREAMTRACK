# benchmark_java_batch.ps1
# Benchmark script for Java Batch Baseline with lazy loading
# Processes full dataset (50 windows, 4500 frames) for fair comparison with streaming

param (
    [int]$Iterations = 3
)

# Detect project root (directory where the script is located)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)
Set-Location $ProjectRoot

$MainClass = "com.espertech.esper.example.IOT.JavaBatchBaseline"
$FeaturesDir = "$ProjectRoot\Datasets\EmbedFeature"
# Reduced dataset: 2 cameras for initial testing
$Cameras = "0001,0002"
$OutputDir = "$ProjectRoot\output\benchmark_java_batch"

if (!(Test-Path $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir }

$Results = @()

function Run-Iteration($IterNum, $LogFile) {
    Write-Host "`n[Iteration $IterNum] Starting Java Batch Baseline (Reduced Dataset)..." -ForegroundColor Cyan
    
    # Reduced dataset: 10 windows (300 frames) for initial testing
    $env:MAX_WINDOWS = "10"
    
    $Args = "--scene 2 --features_dir $FeaturesDir --camera '$Cameras' --output_dir $OutputDir"
    
    # Use Maven exec plugin with increased memory for full dataset
    # Increased to 16g to handle features in memory
    # Use -q to quiet Maven output and avoid interactive prompts
    $Process = Start-Process mvn -ArgumentList "-q exec:java -Dexec.mainClass=`"$MainClass`" `"-Dexec.args=$Args`" -Dcheckstyle.skip=true -Dexec.classpathScope=compile -Dexec.maxMemory=16g" -PassThru -NoNewWindow -RedirectStandardOutput $LogFile -RedirectStandardError "$LogFile.err"
    $Process.WaitForExit()

    # Extract timing metrics from log
    $Content = Get-Content $LogFile -Raw
    
    $Metrics = [PSCustomObject]@{
        Iteration = $IterNum
        LoadFeatures = 0
        WorldCoord = 0
        RepSelection = 0
        MatrixGen = 0
        MatrixZeroing = 0
        SimilarityReplace = 0
        Clustering = 0
        GlobalIDAssign = 0
        GlobalIDReassign = 0
        CoreProcessing = 0
        TotalBatch = 0
    }
    
    if ($Content -match "Stage 1: Load Features & Keypoints:\s+([\d\.]+)\s+ms") {
        $Metrics.LoadFeatures = [double]$Matches[1]
    }
    if ($Content -match "Stage 2: Measure World Coordinates:\s+([\d\.]+)\s+ms") {
        $Metrics.WorldCoord = [double]$Matches[1]
    }
    if ($Content -match "Stage 3: Representative Selection:\s+([\d\.]+)\s+ms") {
        $Metrics.RepSelection = [double]$Matches[1]
    }
    if ($Content -match "Stage 4: Matrix Gen \(Raw\):\s+([\d\.]+)\s+ms") {
        $Metrics.MatrixGen = [double]$Matches[1]
    }
    if ($Content -match "Stage 5: Matrix Zeroing:\s+([\d\.]+)\s+ms") {
        $Metrics.MatrixZeroing = [double]$Matches[1]
    }
    if ($Content -match "Stage 6: Similarity Replace \(World\):\s+([\d\.]+)\s+ms") {
        $Metrics.SimilarityReplace = [double]$Matches[1]
    }
    if ($Content -match "Stage 7: Clustering \(HC\):\s+([\d\.]+)\s+ms") {
        $Metrics.Clustering = [double]$Matches[1]
    }
    if ($Content -match "Stage 8: Global ID Assignment:\s+([\d\.]+)\s+ms") {
        $Metrics.GlobalIDAssign = [double]$Matches[1]
    }
    if ($Content -match "Stage 9: Global ID Reassignment:\s+([\d\.]+)\s+ms") {
        $Metrics.GlobalIDReassign = [double]$Matches[1]
    }
    if ($Content -match "Total Core Processing Time:\s+([\d\.]+)\s+ms") {
        $Metrics.CoreProcessing = [double]$Matches[1]
    }
    if ($Content -match "Total Batch Execution Time:\s+([\d\.]+)\s+ms") {
        $Metrics.TotalBatch = [double]$Matches[1]
    }
    
    return $Metrics
}

for ($i = 1; $i -le $Iterations; $i++) {
    $LogFile = "$OutputDir/log_java_batch_iter$i.txt"
    $Metrics = Run-Iteration $i $LogFile
    $Results += $Metrics
}

# Final Analysis
$AvgLoadFeatures = ($Results.LoadFeatures | Measure-Object -Average).Average
$AvgWorldCoord = ($Results.WorldCoord | Measure-Object -Average).Average
$AvgRepSelection = ($Results.RepSelection | Measure-Object -Average).Average
$AvgMatrixGen = ($Results.MatrixGen | Measure-Object -Average).Average
$AvgMatrixZeroing = ($Results.MatrixZeroing | Measure-Object -Average).Average
$AvgSimilarityReplace = ($Results.SimilarityReplace | Measure-Object -Average).Average
$AvgClustering = ($Results.Clustering | Measure-Object -Average).Average
$AvgGlobalIDAssign = ($Results.GlobalIDAssign | Measure-Object -Average).Average
$AvgGlobalIDReassign = ($Results.GlobalIDReassign | Measure-Object -Average).Average
$AvgCoreProcessing = ($Results.CoreProcessing | Measure-Object -Average).Average
$AvgTotalBatch = ($Results.TotalBatch | Measure-Object -Average).Average

Write-Host "`n" + ("=" * 70) -ForegroundColor Green
Write-Host "JAVA BATCH BASELINE BENCHMARK RESULTS ($Iterations Iterations)" -ForegroundColor Green
Write-Host "Reduced Dataset: 2 cameras, Scene 2, 10 windows (900 frames)" -ForegroundColor Green
Write-Host ("=" * 70) -ForegroundColor Green
Write-Host "Stage 1: Load Features & Keypoints - Average: $([Math]::Round($AvgLoadFeatures, 2)) ms" -ForegroundColor Cyan
Write-Host "Stage 2: Measure World Coordinates  - Average: $([Math]::Round($AvgWorldCoord, 2)) ms" -ForegroundColor Cyan
Write-Host "Stage 3: Representative Selection    - Average: $([Math]::Round($AvgRepSelection, 2)) ms" -ForegroundColor Cyan
Write-Host "Stage 4: Matrix Gen (Raw)           - Average: $([Math]::Round($AvgMatrixGen, 2)) ms" -ForegroundColor Cyan
Write-Host "Stage 5: Matrix Zeroing             - Average: $([Math]::Round($AvgMatrixZeroing, 2)) ms" -ForegroundColor Cyan
Write-Host "Stage 6: Similarity Replace (World) - Average: $([Math]::Round($AvgSimilarityReplace, 2)) ms" -ForegroundColor Cyan
Write-Host "Stage 7: Clustering (HC)            - Average: $([Math]::Round($AvgClustering, 2)) ms" -ForegroundColor Cyan
Write-Host "Stage 8: Global ID Assignment       - Average: $([Math]::Round($AvgGlobalIDAssign, 2)) ms" -ForegroundColor Cyan
Write-Host "Stage 9: Global ID Reassignment     - Average: $([Math]::Round($AvgGlobalIDReassign, 2)) ms" -ForegroundColor Cyan
Write-Host "-" * 70 -ForegroundColor Green
Write-Host "Total Core Processing Time - Average: $([Math]::Round($AvgCoreProcessing, 2)) ms" -ForegroundColor Yellow
Write-Host "Total Batch Execution Time - Average: $([Math]::Round($AvgTotalBatch, 2)) ms" -ForegroundColor Yellow
Write-Host ("=" * 70) -ForegroundColor Green

# Save results to JSON for later comparison
$ResultsJson = $Results | ConvertTo-Json -Depth 3
$ResultsJson | Out-File "$OutputDir/benchmark_java_batch_results.json"

Write-Host "`nResults saved to: $OutputDir\benchmark_java_batch_results.json" -ForegroundColor Gray
