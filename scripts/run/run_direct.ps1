param()

$ProjectRoot = "."
$M2 = "$env:USERPROFILE\.m2\repository"
$ClassPath = @()

# Project classes
$ClassPath += "$ProjectRoot\target\classes"

# Maven dependencies
Get-ChildItem -Path $M2 -Recurse -Filter "*.jar" -ErrorAction SilentlyContinue | 
    Where-Object { $_.FullName -notmatch 'sources|javadoc|tests' } | 
    Select-Object -ExpandProperty FullName |
    ForEach-Object { $ClassPath += $_ }

$cp = $ClassPath -join ';'

Write-Host "Starting JavaBatchBaseline with $($ClassPath.Count) classpath entries..."
java -cp $cp com.espertech.esper.example.IOT.JavaBatchBaseline --scene 1 --features_dir "$ProjectRoot\Datasets\EmbedFeature" --camera 101 --output_dir ./output/bench_batch --debug

$exitCode = $LASTEXITCODE
Write-Host "Exit code: $exitCode"
exit $exitCode
