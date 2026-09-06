# Jetson setup — overnight status (2026-09-06, ~06:00 PDT)

Board: **Jetson Orin Nano (Super) Dev Kit**, JetPack **7.2** / L4T **r39.2.1**, Ubuntu 24.04,
CUDA 13.2.1, aarch64. Repo: `~/billee-software-2027`, branch `B-003-DrivetrainAndTeleopSim`.

## TL;DR

**The simulation path works end-to-end on the Jetson, natively (no container).** You can
build, launch the sim headless, drive it, and view it in Foxglove. See
[docs/RUN_GUIDE.md](docs/RUN_GUIDE.md). Real-hardware (ODESC/CAN) is wired but untested —
no controllers were connected.

## What works (verified)

| # | Item | Result |
|---|------|--------|
| 1 | System package state | A GNOME auto-upgrade was wedged on a `console-setup` debconf prompt with the dpkg lock held. Cleared it, pre-seeded the prompt, `dpkg --configure -a` clean, `apt-get check` clean. |
| 2 | Docker Engine | **29.8.0** installed via JetPack's `nv-install-docker.service` (triggered by `nvidia-container`). `docker.service` enabled + running. |
| 3 | NVIDIA container runtime | `nvidia-container-toolkit 1.19.1`. `/etc/docker/daemon.json` → `"default-runtime": "nvidia"` + `runtimes.nvidia`. `nvidia-ctk cdi list` → `nvidia.com/gpu=all`. |
| 4 | GPU passthrough into a container | `docker run --rm --runtime nvidia ubuntu:24.04 nvidia-smi` → prints the Orin GPU; all `/dev/nvhost-*`, `/dev/nvidia*`, `/dev/nvgpu/igpu0` mounted. |
| 5 | `docker` group | `luquitolanzi` added. **Log out/in once** so `docker` works without `sudo`. |
| 6 | Pixi | `pixi 0.79.0` installed to `~/.pixi` (on PATH via `~/.bashrc`). |
| 7 | `l4t` Pixi env | `cd ros2_ws && pixi install --environment l4t` → OK (RoboStack Humble desktop + Gazebo Fortress + ros2_control + foxglove_bridge, aarch64/CPU). |
| 8 | `colcon build` (native) | `pixi run --environment l4t -- colcon build --parallel-workers 2 --executor sequential …` → **4/4 packages** (`chassis_bringup`, `odesc`, `robot_description`, `teleop`) in ~80 s. Only a CMake-version deprecation warning from `odesc`. |
| 9 | `foxglove_bridge` | Launches, `Server listening on port 8765`, advertises channels. |
| 10 | **Simulation smoke test** | `xvfb-run pixi run --environment l4t ros2 launch chassis_bringup sim_gz.launch.py` → Gazebo Fortress 6.16 headless; hardware `Robot` **active**; `diff_drive_controller` + `joint_state_broadcaster` **active**; all 6 wheel command interfaces claimed; publishing `linear.x=0.5` for 4 s moved `/diff_drive_controller/odom` x from 0 → **0.204 m**. Odometry + TF integrate correctly. |
| 11 | 8 GB swap | Added `/swapfile2` (8 GB, in `/etc/fstab`) so the build doesn't OOM on 7.4 GB RAM. `/swapfile` (2 GB) was already present → 9 GB total. |

## What's wired but NOT verified

- **Real drivetrain (`real.launch.py`)** — no ODESC/CANable connected. `can0` does not exist,
  so `OdescSystemHardware::on_activate` will fail cleanly (controllers stay inactive, no
  motion, robot model still shows). Bring `can0` up first (see RUN_GUIDE §B).
- **L4T container image with the real base** (`nvcr.io/nvidia/l4t-jetpack:r39.2.1`) — **not
  built tonight**: that base is ~10 GB and only ~14 GB is free on `/`. The `Dockerfile.l4t-humble`
  RUN steps were validated by building with `--build-arg IMAGE_NAME=ubuntu:24.04` instead
  (tag `rover-ros2:ubuntu-test`). To use the real base: free disk
  (`docker image prune -a`, remove `ubuntu:24.04`/`rover-ros2:ubuntu-test`) or add storage,
  then `tooling/rover-ros2 build`.
- **VS Code "Dev Containers: Reopen in Container"** — your click. Config is ready:
  `.devcontainer/l4t/devcontainer.json` → `rover-roshumble_l4t-aarch64`.
- **Foxglove Studio / RViz on your laptop** — install/connect is on your side.
  Foxglove: connect to `ws://192.168.4.73:8765` (Jetson LAN IP; re-check with `hostname -I`).
  RViz needs a display (`ssh -X`, a monitor, or the devcontainer with X) — Foxglove is the
  reliable remote path.

## Changes made to the repo (uncommitted, on `B-003-DrivetrainAndTeleopSim`)

| File | Change |
|------|--------|
| `docker/Dockerfile.l4t-humble` | Rewritten: pixi/RoboStack-driven mirror of `Dockerfile.desktop.humble`. Base `nvcr.io/nvidia/l4t-jetpack:r39.2.1` (overridable), non-root `ros_user` (removes the 24.04 default `ubuntu` UID 1000), pixi in `/opt/pixi`, ZED SDK behind `--build-arg INSTALL_ZED=true` (off — no L4T r39 SDK yet). |
| `.devcontainer/l4t/devcontainer.json` | **New.** Mirror of `.devcontainer/devcontainer.json`; `--runtime nvidia` instead of `--gpus all`; `pixi install --environment l4t`. |
| `ros2_ws/pixi.toml` | Added `l4t` environment; added `ros-humble-foxglove-bridge`; renamed feature `mac-cpu` → `aarch64-cpu` (shared by `mac-cpu` and `l4t` envs). |
| `ros2_ws/pixi.lock` | Regenerated (`pixi lock`). All 3 envs resolve. |
| `ros2_ws/src/chassis_bringup/launch/sim_gz.launch.py` | Fixed hardcoded `/workspaces/URC-2027/...envs/default/...` GUI plugin paths — now derived from the active env prefix, and skipped cleanly when headless. |
| `tooling/rover-ros2` | **New.** Parallel to `tooling/desktop-ros2` for the L4T image (`--runtime nvidia`). |
| `README.md` | Added Jetson/L4T section + link to the run guide; host-prep marked done. |
| `docs/RUN_GUIDE.md` | **New.** Step-by-step run guides (sim + real) with a detailed breakdown. |
| `SETUP_STATUS.md` | This file. |

Review with `git -C ~/billee-software-2027 diff` / `git status`. Nothing was committed.

## System changes outside the repo

- Installed: `docker-ce`/`docker-ce-cli`/`containerd.io`/buildx/compose, `nvidia-container*`,
  `pixi` (in `~/.pixi`).
- `/etc/docker/daemon.json` → default-runtime nvidia.
- `luquitolanzi` added to `docker` group.
- `/swapfile2` (8 GB) added + `/etc/fstab` line.
- `console-setup` debconf pre-seeded (`debconf-set-selections`).
- `apt-daily*.timer` and `packagekit` were stopped during the work and **restarted** at the
  end (all `active` again).
- The original GNOME auto-upgrade did **not** fully finish (I interrupted its wedged run).
  Nothing is half-configured, but some packages stayed at old versions. Re-run Software
  Updater or `sudo apt update && sudo apt full-upgrade` at your leisure.

## First thing to try when you wake

```bash
cd ~/billee-software-2027/ros2_ws
export PATH="$HOME/.pixi/bin:$PATH"
xvfb-run -a pixi run --environment l4t ros2 launch chassis_bringup sim_gz.launch.py   # terminal 1
pixi run --environment l4t ros2 launch foxglove_bridge foxglove_bridge_launch.xml     # terminal 2
```

Then Foxglove Studio on your laptop → `ws://192.168.4.73:8765`, fixed frame `odom`, add the
robot model + TF. Publish a Twist to `/diff_drive_controller/cmd_vel_unstamped` (or run the
teleop launch with a gamepad, holding button 5) and watch it move. Full details +
troubleshooting: [docs/RUN_GUIDE.md](docs/RUN_GUIDE.md).
