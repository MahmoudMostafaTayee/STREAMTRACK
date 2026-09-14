@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

REM Build classpath from Maven local repository
set M2=%USERPROFILE%\.m2\repository
set CPFILE=%TEMP%\cp_%RANDOM%.txt

REM Start with project classes
echo target/classes > "%CPFILE%"

REM Add all dependency jars (excluding sources/javadoc/tests)
for /r "%M2%" %%j in (*.jar) do (
    echo %%j | findstr /v "sources javadoc tests" >nul
    if not errorlevel 1 (
        echo %%j >> "%CPFILE%"
    )
)

REM Read the classpath from file (replace newlines with semicolons)
set CP=
for /f "usebackq delims=" %%a in ("%CPFILE%") do (
    set "CP=!CP!%%a;"
)

REM Run
java -cp "!CP!" com.espertech.esper.example.IOT.JavaBatchBaseline --scene 1 --features_dir ".\Datasets\EmbedFeature" --camera 101 --output_dir ./output/bench_batch --debug

del "%CPFILE%" 2>nul
endlocal
