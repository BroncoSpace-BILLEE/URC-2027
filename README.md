# URC-2027

## General Usage

It is generally reccomnded

### System Requirements

for full support:

1. Ubuntu 24+ base OS on device 
2. CUDA v13 (13.2)
3. Docker Engine 
4. VScode with Remote Development Extension group installed

### Pixi

This project uses pixi as the package manager, please make sure that the python interpreter is configured to point to `.pixi/bin/python3` in the devcontainer 

For more information about pixi please look at:
1. [Pixi Cheatsheet](docs/PixiCheatsheet.md)
2. [Pixi in VSCode](https://pixi.prefix.dev/latest/integration/editor/vscode/#python-extension)


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
