package com.espertech.esper.example.IOT.clusterers;

import java.util.LinkedList;
import java.util.Queue;

public class GlobalTrackState {
    public int globalId;
    public long lastSeen;
    public String lastSeenCamera; // camera name where the track was last observed
    public Queue<double[]> recentFeatures;
    public static final int MAX_FEATURES = 10; // keep last 10 features

    public GlobalTrackState(int globalId, long timestamp, String camera) {
        this.globalId = globalId;
        this.lastSeen = timestamp;
        this.lastSeenCamera = camera;
        this.recentFeatures = new LinkedList<>();
    }

    public synchronized void addFeature(double[] feature) {
        if (feature == null)
            return;
        if (recentFeatures.size() >= MAX_FEATURES) {
            recentFeatures.poll();
        }
        recentFeatures.add(feature);
    }

    public synchronized void updateLastSeen(long timestamp) {
        this.lastSeen = timestamp;
    }

    public synchronized void updateLastSeen(long timestamp, String camera) {
        this.lastSeen = timestamp;
        this.lastSeenCamera = camera;
    }
}
