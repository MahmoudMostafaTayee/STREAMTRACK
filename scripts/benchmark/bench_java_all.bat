@echo off
set MAIN_CLASS=com.espertech.esper.example.IOT.IotMain
set FEATURES_DIR=.\Datasets\EmbedFeature

echo Running Java All-in-one Grouping (1 Window benchmark)...
mvn exec:java -Dexec.mainClass="%MAIN_CLASS%" "-Dexec.args=--scene 2 --features_dir %FEATURES_DIR% --camera all --camera_groups all --turbo --output_dir ./output/bench_all" -Dcheckstyle.skip=true
