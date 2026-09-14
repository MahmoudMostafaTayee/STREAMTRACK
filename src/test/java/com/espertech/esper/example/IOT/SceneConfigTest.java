package com.espertech.esper.example.IOT;

import com.espertech.esper.example.IOT.helpers.ErrorCode;
import com.espertech.esper.example.IOT.helpers.TrackingParameters;
import org.junit.AfterClass;
import org.junit.BeforeClass;
import org.junit.Test;

import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

/**
 * Regression tests for scene-parameter loading
 * ({@link TrackingParameters#getTrackingParams(String[])} ->
 * {@code getParametersForScene}).
 *
 * <p>These tests exercise the public CLI entry point so the full precedence
 * chain (class defaults &lt; scene config &lt; CLI) is covered.</p>
 */
public class SceneConfigTest {

    private static Path overrideDir;
    private static Path overrideFile;
    private static double savedSimTh;
    private static double savedEpsilonMcpt;
    private static int savedFps;
    private static String savedClusteringMethod;
    private static String savedFeaturesDir;
    private static String savedOutputDir;
    private static int savedScene;

    @BeforeClass
    public static void setUp() throws IOException {
        overrideDir = Paths.get("config");
        overrideFile = overrideDir.resolve("scene_001.json");
        Files.createDirectories(overrideDir);
        Files.write(overrideFile, (
                "{\n"
              + "  \"_comment\": \"Temporary test override\",\n"
              + "  \"simTh\": 0.85,\n"
              + "  \"epsilonMcpt\": 0.35,\n"
              + "  \"fps\": 25\n"
              + "}\n").getBytes(StandardCharsets.UTF_8));

        savedSimTh = TrackingParameters.simTh;
        savedEpsilonMcpt = TrackingParameters.epsilonMcpt;
        savedFps = TrackingParameters.fps;
        savedClusteringMethod = TrackingParameters.clustering_method;
        savedFeaturesDir = TrackingParameters.FEATURES_BASE_DIR;
        savedOutputDir = TrackingParameters.OUTPUT_DIR;
        savedScene = TrackingParameters.scene;
    }

    @AfterClass
    public static void tearDown() throws IOException, ReflectiveOperationException {
        Files.deleteIfExists(overrideFile);
        setField("simTh", savedSimTh);
        setField("epsilonMcpt", savedEpsilonMcpt);
        setField("fps", savedFps);
        setField("clustering_method", savedClusteringMethod);
        setField("FEATURES_BASE_DIR", savedFeaturesDir);
        setField("OUTPUT_DIR", savedOutputDir);
        setField("scene", savedScene);
    }

    private static void setField(String name, Object value) throws ReflectiveOperationException {
        Field f = TrackingParameters.class.getField(name);
        f.set(null, value);
    }

    private static void run(String[] args) {
        assertEquals(ErrorCode.SUCCESS, TrackingParameters.getTrackingParams(args));
    }

    /** A top-level config/scene_NNN.json overrides the shipped scene defaults. */
    @Test
    public void topLevelOverrideWins() {
        run(new String[]{"--scene", "1", "--features_dir", "./Datasets/EmbedFeature",
                "--output_dir", "./output/test"});
        assertEquals(0.85, TrackingParameters.simTh, 1e-9);
        assertEquals(0.35, TrackingParameters.epsilonMcpt, 1e-9);
        assertEquals(25, TrackingParameters.fps);
    }

    /** The shipped config/scenes/scene_NNN.json loads when no override exists. */
    @Test
    public void shippedSceneDefaultsLoad() {
        run(new String[]{"--scene", "2", "--features_dir", "./Datasets/EmbedFeature",
                "--output_dir", "./output/test"});
        assertEquals(0.37, TrackingParameters.epsilonMcpt, 1e-9);
        assertEquals("agglomerative", TrackingParameters.clustering_method);
        assertEquals(34, countSceneConfigKeys("scene_002.json")); // 33 params + _comment
    }

    /** An explicit CLI flag beats whatever the scene config set. */
    @Test
    public void cliFlagBeatsSceneConfig() {
        run(new String[]{"--scene", "1", "--features_dir", "./Datasets/EmbedFeature",
                "--clusterer", "clustream", "--output_dir", "./output/test"});
        assertEquals("clustream", TrackingParameters.clustering_method);
    }

    /** Missing config files leave class defaults untouched. */
    @Test
    public void missingConfigKeepsDefaults() {
        double before = TrackingParameters.simTh;
        run(new String[]{"--scene", "999", "--features_dir", "./Datasets/EmbedFeature",
                "--output_dir", "./output/test"});
        assertEquals(before, TrackingParameters.simTh, 1e-9);
        assertTrue(TrackingParameters.scene == 999);
    }

    private static int countSceneConfigKeys(String fileName) {
        try {
            String json = new String(Files.readAllBytes(
                    Paths.get("config", "scenes", fileName)), StandardCharsets.UTF_8);
            return com.google.gson.JsonParser.parseString(json).getAsJsonObject().size();
        } catch (IOException e) {
            return -1;
        }
    }
}
