package com.espertech.esper.example.IOT.streams;

/**
 * Represents a topology edge between two cameras.
 * <p>
 * {@code overlapping} indicates whether the cameras share a physical field-of-view overlap.
 * Overlapping edges are used for real-time stream joins (EPL aggregation).
 * Non-overlapping (transition) edges are used only for Re-ID candidate filtering.
 */
public class CameraTopology {
    private String cameraId;
    private String neighborId;
    private boolean enabled;
    private boolean overlapping;

    /**
     * Full constructor specifying overlap type.
     */
    public CameraTopology(String cameraId, String neighborId, boolean enabled, boolean overlapping) {
        this.cameraId = cameraId;
        this.neighborId = neighborId;
        this.enabled = enabled;
        this.overlapping = overlapping;
    }

    public String getCameraId() {
        return cameraId;
    }

    public String getNeighborId() {
        return neighborId;
    }

    public boolean isEnabled() {
        return enabled;
    }

    public boolean isOverlapping() {
        return overlapping;
    }
}
