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

This project uses pixi as the package manager, please make sure that the python interpreter is configured to point to `.pixi/envs/default/bin/python3` in the devcontainer 

For more information about pixi please look at:
1. [Pixi Cheatsheet](docs/PixiCheatSheet.md)
2. [Pixi in VSCode](https://pixi.prefix.dev/latest/integration/editor/vscode/#python-extension)

### Running the drivetrain

See **[docs/RUN_GUIDE.md](docs/RUN_GUIDE.md)** — step-by-step for the simulation (no
hardware) and the real ODESC drivetrain, followed by a full breakdown of how each launch
file works. Live status / handoff notes: **[HANDOFF_CHECKPOINT.md](HANDOFF_CHECKPOINT.md)**.

## Drivetrain architecture

One control stack, three interchangeable backends. `diff_drive_controller` only ever
sees wheel-joint `position`/`velocity` interfaces, so the **same controller, topics,
odometry and TF** work whether the numbers come from Gazebo physics, a real Hall
encoder over CAN, or a hardware-free loopback. The backend is chosen by the
`use_sim` xacro arg (`sim_gz.launch.py` → Gazebo; `real.launch.py` → CAN) and, for
the real path, the `can_interface` launch arg (`can0` real / `vcan0` virtual bus /
`mock` loopback).

```mermaid
flowchart TB
    subgraph OP["Operator / ground station"]
        PAD["Xbox controller<br/>/dev/input/js0"]
        FGS["Foxglove Studio<br/>(laptop, ws://rover:8765)"]
        RVIZ_UI["RViz2 window<br/>(display / xvfb)"]
    end

    subgraph TELE["teleop  (teleop pkg)"]
        JOY["joy_node<br/>joystick.yaml"]
        TANK["joy_tank_drive<br/>tank mix + button-5 deadman"]
    end
    PAD -->|USB| JOY
    JOY -->|"/joy  sensor_msgs/Joy"| TANK
    TANK -->|"/diff_drive_controller/cmd_vel_unstamped<br/>geometry_msgs/Twist"| DDC

    subgraph CTRL["ros2_control  (controller_manager)"]
        direction TB
        DDC["diff_drive_controller<br/>DiffDriveController"]
        JSB["joint_state_broadcaster"]
        RM["resource_manager<br/>loads ONE &lt;hardware&gt; plugin"]
        DDC <-->|"6× wheel joint<br/>vel cmd / pos+vel state (rad, rad/s)"| RM
        JSB -->|"/joint_states"| RSP
        DDC -->|"/diff_drive_controller/odom + odom→base_link TF"| TF
    end
    CFG["robot_description/config/controllers.yaml<br/>wheel lists · 0.67 m sep · 0.11 m radius"] -.-> DDC
    URDF["robot_description URDF (xacro)<br/>use_sim · ros2_control.urdf.xacro"] -.-> RM

    subgraph BE["swappable hardware backend  (resource_manager plugin)"]
        direction TB
        subgraph SIMB["use_sim:=true — sim_gz.launch.py"]
            IGN["ign_ros2_control/IgnitionSystem"]
            GZ["Gazebo Fortress · empty.sdf<br/>physics + wheel actuators"]
            BR["ros_gz_bridge → /clock"]
            IGN <--> GZ
            GZ --> BR
        end
        subgraph REALB["use_sim:=false — real.launch.py"]
            ODESC["odesc/OdescSystemHardware<br/>gear_ratio 48:1 · SocketCAN"]
            subgraph CANMODE["can_interface"]
                CAN0["can0 → 6× ODESC V4.2 + NEO<br/>ODrive CANSimple 0.5.x @ 500 kbit/s"]
                VCAN["vcan0 → virtual bus (candump/cansend)"]
                MOCK["mock/none → gear-ratio loopback<br/>(no CAN, no motors)"]
            end
            ODESC --> CANMODE
        end
    end
    RM --- SIMB
    RM --- REALB

    ODESC -->|"TX 0x0D Set_Input_Vel (write)<br/>0x07 Set_Axis_Requested_State (activate/deactivate)"| CAN0
    CAN0 -->|"RX 0x09 Get_Encoder_Estimates<br/>motor turns / turns·s⁻¹"| ODESC

    subgraph STATE["state / TF"]
        RSP["robot_state_publisher<br/>URDF kinematics"]
        TF["/tf · /tf_static"]
        RSP --> TF
    end

    subgraph VIZ["visualization  (chassis_bringup/viz.launch.py)"]
        FB["foxglove_bridge  :8765"]
        RVIZ["rviz2  -d drivetrain.rviz"]
    end
    TF --> FB
    TF --> RVIZ
    RSP -->|"/robot_description"| FB
    RSP -->|"/robot_description"| RVIZ
    DDC -->|"/diff_drive_controller/odom"| FB
    DDC -->|"/diff_drive_controller/odom"| RVIZ
    FB <-->|WebSocket| FGS
    RVIZ --> RVIZ_UI
```

**Layers, bottom to top:** physical/OS (`can0` via `tooling/can-up`, Tegra `mttcan`
@ 500 kbit/s) → driver (`odesc/OdescSystemHardware`, ODrive CANSimple subset, the
only place the **48:1** motor↔wheel gear ratio is applied) → `ros2_control`
(`resource_manager` + `diff_drive_controller` + `joint_state_broadcaster`, config in
`controllers.yaml`) → ROS graph (`/…/cmd_vel_unstamped`, `/…/odom`, `/joint_states`,
`/tf`) → teleop (`joy_node` → `joy_tank_drive`) and visualization
(`foxglove_bridge` :8765 for the remote ground station, `rviz2` for a local
display). Canonical CAN node-ID ↔ wheel map: `ros2_ws/src/odesc/config/node_map.yaml`.

### CAN frame layout (ODrive CANSimple, real backend)

```mermaid
flowchart LR
    A["11-bit arbitration ID<br/>= (node_id &lt;&lt; 5) | cmd_id"] --> B{cmd_id}
    B -->|"0x07 TX"| C["Set_Axis_Requested_State<br/>u32 LE: 8=CLOSED_LOOP on activate, 1=IDLE on stop"]
    B -->|"0x0D TX / write()"| D["Set_Input_Vel<br/>f32 LE vel = wheel_rad_s × 48 / 2π ; torque_ff = 0"]
    B -->|"0x09 RX / read()"| E["Get_Encoder_Estimates (cyclic)<br/>f32 LE pos,vel → wheel = motor × 2π / 48"]
```


## Apple-Silicon CPU devcontainer

The default devcontainer is for Linux hosts with an NVIDIA GPU and a ZED camera.
For local CPU-only development on an Apple-Silicon Mac, use the `Mac` configuration
in `.devcontainer/mac/devcontainer.json` (VS Code: **Dev Containers: Reopen in
Container**, then select **desktop-roshumble-mac-cpu**).

This configuration intentionally excludes CUDA, the ZED SDK, GPU/device forwarding,
and physical-robot networking. It uses the separate `mac-cpu` Pixi environment
(backed by the shared `aarch64-cpu` feature):

```sh
cd ros2_ws
pixi install --environment mac-cpu
pixi run --environment mac-cpu build
```

X11/XQuartz GUI forwarding must be configured by users invidually

## NVIDIA Jetson (L4T) rover devcontainer

For the rover itself — an NVIDIA Jetson (Orin-family or Thor) flashed with
**JetPack 7.2 / L4T r39.2.x** — use the `l4t` configuration in
`.devcontainer/l4t/devcontainer.json` (VS Code: **Dev Containers: Reopen in
Container**, then select **rover-roshumble_l4t-aarch64**).

It mirrors the default devcontainer's pixi/RoboStack structure but builds
`docker/Dockerfile.l4t-humble` (base `nvcr.io/nvidia/l4t-jetpack:r39.2.1`) and
forwards the GPU with the `nvidia` container runtime instead of `--gpus all`
(unreliable on JetPack 7). ROS 2 Humble comes from the aarch64 `l4t` Pixi
environment (shared `aarch64-cpu` feature). The ZED SDK is gated off
(`--build-arg INSTALL_ZED=true` once a matching L4T r39 SDK ships).

Host prep on the Jetson (one-time — **already done on the current BILLEE Orin Nano**):

```sh
sudo apt install -y nvidia-container curl   # JetPack 7.2: pulls nvidia-container-toolkit
                                            # and runs nv-install-docker.service (installs
                                            # Docker CE + wires the nvidia runtime)
# then, for GPU access at build time too:
#   /etc/docker/daemon.json -> "default-runtime": "nvidia"
sudo usermod -aG docker "$USER"   # then log out / back in
docker run --rm --runtime nvidia ubuntu:24.04 nvidia-smi   # smoke test
```

> On JetPack 7 use `--runtime nvidia`, not `--gpus all`.

The native (no-container) path is also fully set up on this Jetson: Pixi is installed and
the `l4t` environment is built — see [docs/RUN_GUIDE.md](docs/RUN_GUIDE.md).

Inside the container (first build throttled — Orin Nano has 8 GB RAM):

```sh
cd ros2_ws
pixi run --environment l4t -- colcon build --symlink-install \
  --parallel-workers 2 --executor sequential \
  --event-handlers console_direct+ --base-paths src \
  --cmake-args ' -DCMAKE_BUILD_TYPE=Release'
pixi run --environment l4t build            # later incremental builds
pixi run --environment l4t ros2 launch chassis_bringup real.launch.py            # real ODESC/CAN
pixi run --environment l4t ros2 launch chassis_bringup real.launch.py can_interface:=mock  # no motors
pixi run --environment l4t ros2 launch chassis_bringup viz.launch.py            # rviz + foxglove :8765
```

Set the VS Code Python interpreter to `.pixi/envs/l4t/bin/python3`.
On the ground station (x86 laptop, default devcontainer) open Foxglove Studio and
connect to `ws://<rover-ip>:8765`.

Without VS Code, `tooling/rover-ros2 build|run|shell` builds and runs the same image.
