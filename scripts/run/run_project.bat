@echo off
REM Run script for Esper IOT Example
REM Bypasses checkstyle and uses Maven to run the project with specified arguments.

set MAIN_CLASS=com.espertech.esper.example.IOT.IotMain
set ARGS=--scene 1 --features_dir .\Datasets\EmbedFeature --camera all --output_dir ./output/scene1

mvn exec:java -Dexec.mainClass="%MAIN_CLASS%" -Dexec.args="%ARGS%" -Dcheckstyle.skip
