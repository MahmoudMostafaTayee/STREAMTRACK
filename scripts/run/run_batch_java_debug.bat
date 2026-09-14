@echo off
set MAIN_CLASS=com.espertech.esper.example.IOT.JavaBatchBaseline
set FEATURES_DIR=.\Datasets\EmbedFeature

echo Running Java Batch Baseline (Scene 1, debug mode)...
mvn exec:java -Dexec.mainClass="%MAIN_CLASS%" "-Dexec.args=--scene 1 --features_dir %FEATURES_DIR% --camera all --output_dir ./output/bench_batch --debug" -Dcheckstyle.skip=true
pause
