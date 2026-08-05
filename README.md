# URC-2027

## Apple-Silicon CPU devcontainer

The default devcontainer is for Linux hosts with an NVIDIA GPU and a ZED camera.
For local CPU-only development on an Apple-Silicon Mac, use the `Mac` configuration
in `.devcontainer/mac/devcontainer.json` (VS Code: **Dev Containers: Reopen in
Container**, then select **desktop-roshumble-mac-cpu**).

This configuration intentionally excludes CUDA, the ZED SDK, GPU/device forwarding,
and physical-robot networking. It uses the separate `mac-cpu` Pixi environment:

```sh
cd ros2_ws
pixi install --environment mac-cpu
pixi run --environment mac-cpu build
```

X11/XQuartz GUI forwarding must be configured by users invidually
