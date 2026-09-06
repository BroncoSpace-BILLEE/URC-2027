# BILLEE Drivetrain — Run Guide

Two ways to bring up the drivetrain:

- **A. Simulation** — Gazebo, no motor hardware. Use this to check the whole stack works.
- **B. Real drivetrain** — six ODESC/ODrive controllers over CAN.

All commands run on the **Jetson**, from `~/billee-software-2027/ros2_ws`, through the
`l4t` Pixi environment. Every terminal needs the same prefix:

```bash
cd ~/billee-software-2027/ros2_ws
export PATH="$HOME/.pixi/bin:$PATH"      # once per shell (or add to ~/.bashrc)
```

`pixi run --environment l4t <cmd>` runs `<cmd>` with ROS 2 + the built workspace already
sourced. `pixi shell --environment l4t` drops you into a shell where that's done once.

---

## QUICK START

### One-time: build the workspace

```bash
cd ~/billee-software-2027/ros2_ws
export PATH="$HOME/.pixi/bin:$PATH"
pixi run --environment l4t -- colcon build --symlink-install \
  --parallel-workers 2 --executor sequential --base-paths src \
  --cmake-args ' -DCMAKE_BUILD_TYPE=Release'
```

Rebuild after code changes with the short form: `pixi run --environment l4t build`

Check it worked:

```bash
pixi run --environment l4t ros2 pkg list | grep -E 'chassis_bringup|odesc|robot_description|teleop'
```

All four must print.

---

### A. SIMULATION (no ODESC hardware)

**Terminal 1 — sim + robot + controllers**

```bash
cd ~/billee-software-2027/ros2_ws && export PATH="$HOME/.pixi/bin:$PATH"
xvfb-run -a pixi run --environment l4t ros2 launch chassis_bringup sim_gz.launch.py
```

(Drop `xvfb-run -a` if the Jetson has a monitor / you want the Gazebo window.)

**Terminal 2 — viewers (RViz + Foxglove bridge)**

```bash
cd ~/billee-software-2027/ros2_ws && export PATH="$HOME/.pixi/bin:$PATH"
# both viewers, sim clock:
xvfb-run -a pixi run --environment l4t ros2 launch chassis_bringup viz.launch.py use_sim_time:=true
# foxglove only (headless rover, view from a laptop):
pixi run --environment l4t ros2 launch chassis_bringup viz.launch.py rviz:=false use_sim_time:=true
```

`viz.launch.py` starts `rviz2 -d chassis_bringup/rviz/drivetrain.rviz` (RobotModel +
TF + `/diff_drive_controller/odom`, fixed frame `odom`) and `foxglove_bridge` on
`:8765`. You can also fold the viewers into the sim launch itself:
`ros2 launch chassis_bringup sim_gz.launch.py rviz:=true foxglove:=true`.

**Terminal 3 — gamepad (plug it into the Jetson)**

```bash
cd ~/billee-software-2027/ros2_ws && export PATH="$HOME/.pixi/bin:$PATH"
pixi run --environment l4t ros2 launch teleop teleop.launch.py
```

**On your laptop — see it:**
- **Foxglove Studio** → *Open connection* → `ws://192.168.4.73:8765`
  Add a 3D panel, set *Display frame* / *Fixed frame* to `odom`, enable the robot model + TF.
- or **RViz** on the Jetson (needs a display; `viz.launch.py` above already starts it,
  or `pixi run --environment l4t rviz2 -d src/chassis_bringup/rviz/drivetrain.rviz`).

**Drive:** hold the **safety button** (gamepad button 5 — a shoulder/bumper) and push the
sticks. Left stick = left track, right stick = right track (tank drive). Release the button
= stop.

**Check without a gamepad:**

```bash
pixi run --environment l4t ros2 topic pub -r 10 /diff_drive_controller/cmd_vel_unstamped \
  geometry_msgs/msg/Twist '{linear: {x: 0.4}, angular: {z: 0.3}}'
```

The robot should move in Gazebo and the `odom` frame should drift in Foxglove/RViz.

---

### B. REAL DRIVETRAIN (ODESC over CAN)

**Terminal 1 — bring up the CAN bus.** Use the helper (bitrate **500000**, matching
`BILLEE_NEO_ODESC_Hardware_Integration_Guide.md` §3.4):

```bash
~/billee-software-2027/tooling/can-up            # can0 @ 500 kbit/s (real ODESC bus)
~/billee-software-2027/tooling/can-up status can0
candump can0                                     # optional: ODESC heartbeat frames (cmd 0x01)
```

Persist it across reboots with `tooling/can0.service`
(`sudo cp … /etc/systemd/system/ && sudo systemctl enable --now can0.service`).

**Terminal 2 — drivetrain**

```bash
cd ~/billee-software-2027/ros2_ws && export PATH="$HOME/.pixi/bin:$PATH"
pixi run --environment l4t ros2 launch chassis_bringup real.launch.py
#   gear_ratio:=48.0    (default; ODESC V4.2 + NEO REV v1.1 — override if the gearbox differs)
#   can_interface:=can0 (default) | vcan0 (virtual bus) | mock (no CAN, loopback feedback)
#   rviz:=true foxglove:=true   (fold the viewers in)
```

**No motor controllers yet?** Two hardware-free options, both exercise the real
control stack (not Gazebo) end to end — encoder feedback → `/odom` → TF → viewer:

```bash
# 1) mock: OdescSystemHardware runs a 48:1 gear-ratio loopback of the command.
pixi run --environment l4t ros2 launch chassis_bringup real.launch.py can_interface:=mock rviz:=true

# 2) vcan0: a virtual CAN bus you can watch/inject with candump/cansend.
~/billee-software-2027/tooling/can-up vcan0
pixi run --environment l4t ros2 launch chassis_bringup real.launch.py can_interface:=vcan0
candump -L vcan0        # see Set_Axis_Requested_State (0x07) + Set_Input_Vel (0x0D)
# inject encoder feedback for node 3 (joint_wheel_r1), pos=2.0 turns / vel=1.0 tps:
cansend vcan0 069#000000400000803F
```

**Terminal 3 — viewers** — same as sim but `use_sim_time:=false` (wall clock):
`ros2 launch chassis_bringup viz.launch.py use_sim_time:=false`.

**Terminal 4 — gamepad** — same as sim (`ros2 launch teleop teleop.launch.py`).

> `real.launch.py` hands the standalone `controller_manager` a temp copy of
> `controllers.yaml` with `use_sim_time: false`. This is required: a standalone
> `ros2_control_node` started with `use_sim_time:=true` and no `/clock` freezes its
> update loop and `load_controller` hangs forever. `controllers.yaml` itself is
> unchanged (Gazebo still needs `use_sim_time: true`).

**Verify the hardware came up:**

```bash
pixi run --environment l4t ros2 control list_hardware_components   # 'Robot' should be ACTIVE
pixi run --environment l4t ros2 control list_controllers           # both 'active'
```

If `can0` is missing or the bus is wrong, the launch still starts but the hardware stays
`unconfigured`, the controllers stay `inactive`, and the wheels won't move (see
Troubleshooting).

**Drive:** same safety-button + sticks as sim.

---
---

## HOW IT WORKS

### Pixi environments

`ros2_ws/pixi.toml` defines three environments over one `pixi.lock`:

| env | platform | used by |
|-----|----------|---------|
| `default` | linux-64 + CUDA | x86 ground-station devcontainer |
| `mac-cpu` | linux-aarch64 | Apple-Silicon dev |
| `l4t` | linux-aarch64 | **this Jetson** (and the `.devcontainer/l4t` container) |

`l4t` and `mac-cpu` share the `aarch64-cpu` feature: RoboStack ROS 2 Humble desktop +
Gazebo Fortress + `ros2_control` + `foxglove_bridge`, all CPU (no CUDA/ZED). The
`[activation]` block auto-sources `install/setup.sh`, so after the first `colcon build`
every `pixi run --environment l4t …` already has the workspace overlay.

The **container** path is identical software: `.devcontainer/l4t/devcontainer.json` builds
`docker/Dockerfile.l4t-humble` (base `nvcr.io/nvidia/l4t-jetpack:r39.2.1`), forwards the
GPU with `--runtime nvidia`, and runs the same `pixi install --environment l4t`. Open it
from VS Code: *Dev Containers: Reopen in Container* → `rover-roshumble_l4t-aarch64`. The
native path above needs no container.

### `use_sim` selects the hardware backend

`robot_description/urdf/ros2_control.urdf.xacro` has one `<ros2_control>` block whose
`<hardware>` plugin is chosen by the `use_sim` xacro arg:

- `use_sim:=true` (default) → `ign_ros2_control/IgnitionSystem` — simulated actuators
  inside Gazebo. **No CAN, no `can0`, no ODESCs.**
- `use_sim:=false` → `odesc/OdescSystemHardware` — a `ros2_control` `SystemInterface` that
  opens Linux SocketCAN (`can0`) and speaks the ODrive "CAN Simple" protocol (v0.5.4) to
  six nodes, IDs 0–5 (map: `odesc/config/node_map.yaml`).

`sim_gz.launch.py` passes no arg (so `use_sim=true`); `real.launch.py` passes
`use_sim:=false`.

### What `sim_gz.launch.py` starts

1. **Gazebo Fortress** (`ros_gz_sim`), world `empty.sdf`, running (`-r`).
2. **`robot_state_publisher`** — publishes `/robot_description` + `/tf` from the xacro,
   `use_sim_time:=true`.
3. **`ros_gz_bridge`** — bridges `/clock` (and anything added to
   `chassis_bringup/config/config.yaml`) Gazebo→ROS.
4. **`create`** — spawns the robot (`BILLEE_BOT`) from `/robot_description`.
5. **controller spawners** — `joint_state_broadcaster` + `diff_drive_controller`
   (`robot_description/config/controllers.yaml`). Gazebo hosts the `controller_manager`
   via the `ign_ros2_control` plugin.

`diff_drive_controller` consumes `/diff_drive_controller/cmd_vel_unstamped`, drives the six
wheel joints, integrates wheel odometry, and publishes `/diff_drive_controller/odom` +
the `odom → base_link` TF (`enable_odom_tf: true`). That TF is what makes the robot move
on screen.

> **Headless note:** the launch file starts Gazebo *with* its GUI. Over SSH with no
> display that GUI can't open, so we wrap it in `xvfb-run` (a throwaway virtual display) —
> physics, `ros2_control` and all topics run normally; you just don't see the Gazebo
> window. Use Foxglove/RViz for the picture. On a Jetson with a monitor, skip `xvfb-run`.
>
> `sim_gz.launch.py` also sets two `IGN_GUI_PLUGIN_PATH` / `QML2_IMPORT_PATH` values that
> were hardcoded to an old path (`/workspaces/URC-2027/...envs/default/...`). They are
> only needed for the Gazebo GUI's own panels and are harmless when wrong under
> `xvfb-run`; if you run the real Gazebo GUI and its side panels are missing, fix those
> two lines to point at `…/ros2_ws/.pixi/envs/l4t/lib/ign-gazebo-6/plugins/gui`.

### What `real.launch.py` starts

Same `robot_description` + same `controllers.yaml`, but:

- xacro expanded with `use_sim:=false can_interface:=<arg> gear_ratio:=<arg>` →
  `OdescSystemHardware` loaded.
- a **standalone `controller_manager`** (`ros2_control_node`), given `robot_description`
  as a parameter and a **temp copy of `controllers.yaml` with `use_sim_time: false`**
  (see the box in section B — this is load-bearing, not cosmetic).
- `use_sim_time:=false` everywhere (wall clock).
- same `joint_state_broadcaster` + `diff_drive_controller` spawners.
- the `viz.launch.py` include (`rviz:=`/`foxglove:=`, default off).

Lifecycle: `on_init` validates params/interfaces and picks mock mode when
`can_interface` is `mock`/`none`. `on_activate` opens the SocketCAN socket and sends
`Set_Axis_Requested_State → CLOSED_LOOP_CONTROL (8)` to all six nodes — with a real
`can0` that is missing/misconfigured this fails cleanly (component stays
`unconfigured`, wheels dead). `read()` converts `Get_Encoder_Estimates` motor
turns → wheel rad via the **48:1** ratio; `write()` does the inverse into
`Set_Input_Vel`. Mock mode skips the socket and loops the command back through the
same ratio so `/odom`/TF/viewers still work with no motors.

### The teleop chain

`teleop.launch.py` starts:

- **`joy_node`** (`joy` pkg) — reads the USB gamepad (`/dev/input/js0`), publishes `/joy`.
  Params from `teleop/config/joystick.yaml` (`device_id: 0`, `deadzone: 0.05`).
- **`joy_tank_drive`** (`teleop/src/joy_teleop.cpp`) — subscribes `/joy`, publishes
  `Twist`, **remapped to `/diff_drive_controller/cmd_vel_unstamped`**.
  - `left_axis: 1`, `right_axis: 4`, `max_vel: 2.0` (m/s and rad/s scale).
  - `safety_button: 5` — twist is **zero unless button 5 is held**. This is a deadman.
  - `linear.x = (L+R)/2 · max_vel`, `angular.z = (R−L)/2 · max_vel` — tank mixing.

Same chain drives sim and real; only the `controller_manager` behind the topic differs.

### Visualizing — Foxglove vs RViz

- **`foxglove_bridge`** exposes every ROS topic over one WebSocket on `:8765`. Foxglove
  Studio (laptop app or browser) connects to `ws://<jetson-ip>:8765` — no ROS on the
  laptop, one TCP connection (works over the rover radio link). This is the intended
  ground-station path.
- **RViz** is a native ROS node — it must run somewhere with ROS and a display (the
  Jetson with a monitor, or `ssh -X`, or the devcontainer with X forwarding). Same 3D
  content; better for interactive markers / MoveIt, worse over a network.
- Both can run at once. For either, set the fixed frame to **`odom`**.

### `use_sim_time`

In sim, `robot_state_publisher`, `controller_manager` and the controllers all run with
`use_sim_time:=true` and follow Gazebo's `/clock`. Anything else you start against the sim
(RViz, `foxglove_bridge`, `ros2 topic echo`) should also get `--ros-args -p use_sim_time:=true`
or TF timestamps will look stale — `viz.launch.py use_sim_time:=true` handles this.

`real.launch.py` runs everything on the **wall clock** and *must*: a standalone
`ros2_control_node` with `use_sim_time:=true` but no `/clock` publisher has a frozen
RT update loop, and `load_controller` then blocks forever (every "real" bring-up
would wedge at *"Loading controller 'diff_drive_controller'"*). The launch guarantees
this by generating a wall-clock copy of `controllers.yaml`. If you ever run
`ros2_control_node` by hand, pass `-p use_sim_time:=false`.

> The warning `Could not enable FIFO RT scheduling policy: Operation not permitted`
> from `ros2_control_node` is harmless here — the loop just runs at `SCHED_OTHER`.
> For low-jitter real driving, grant the user `rtprio` (`/etc/security/limits.d/`,
> or run under a systemd unit with `AmbientCapabilities=CAP_SYS_NICE` /
> `LimitRTPRIO=`). `setcap` on the conda binary does **not** work — it trips
> `AT_SECURE` and the env's `LD_LIBRARY_PATH` is then ignored.

### CAN bring-up (real only)

`can0` / `vcanN` are not up by default. Use **`tooling/can-up`**:

```bash
tooling/can-up            # can0 @ 500000 bit/s, restart-ms 100  (real ODESC bus)
tooling/can-up can0 250000   # override the bitrate
tooling/can-up vcan0     # create + up a virtual bus for hardware-free testing
tooling/can-up down vcan0
tooling/can-up status can0
```

Bitrate **500000** matches `BILLEE_NEO_ODESC_Hardware_Integration_Guide.md` §3.4
(`odrv0.can.config.baud_rate = 500000`) — confirm against the actual ODESC firmware
before trusting it. Persist `can0` with `tooling/can0.service`
(`sudo cp tooling/can0.service /etc/systemd/system/ && sudo systemctl enable --now can0.service`).
`odesc/config/node_map.yaml` is the canonical node-ID ↔ wheel map; the per-joint
`<param name="node_id">` values in `ros2_control.urdf.xacro` are hand-copied from it —
keep them in sync.

### Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `colcon build` killed / machine unresponsive | RAM pressure (8 GB board). Keep `--parallel-workers 2 --executor sequential`; a `/swapfile2` (8 GB) is already active. |
| Gazebo GUI window never appears over SSH | Expected. Use `xvfb-run -a …` and view in Foxglove/RViz. |
| Foxglove "connection refused" | `foxglove_bridge` not running, or wrong IP. `hostname -I` on the Jetson; port is `8765`. |
| robot model shows but never moves (sim) | teleop safety button not held; or nothing publishing `/diff_drive_controller/cmd_vel_unstamped` (`ros2 topic echo` it). |
| `real.launch.py`: wheels dead, `ros2 control list_controllers` shows `inactive` | `can0` down or wrong bitrate → `OdescSystemHardware` `on_activate` failed. `tooling/can-up` first; check `dmesg` / node logs. To bring the stack up with no motors, use `can_interface:=mock` or `:=vcan0`. |
| `real.launch.py` hangs at *"Loading controller 'diff_drive_controller'"*, `spawner` "Failed getting a result from … list_controllers" | Standalone `ros2_control_node` running with `use_sim_time:=true` and no `/clock` — frozen RT loop. `real.launch.py` fixes this automatically; if you hand-rolled the CM, pass `-p use_sim_time:=false`. |
| `ros2_control_node`: `Could not enable FIFO RT scheduling policy` | Harmless — runs at `SCHED_OTHER`. For jitter-free real driving grant `rtprio` via `/etc/security/limits.d/` or a systemd unit (`AmbientCapabilities=CAP_SYS_NICE`). Not `setcap` (breaks conda lib lookup). |
| `real.launch.py can_interface:=vcan0` but no frames | `tooling/can-up vcan0` first; `candump -L vcan0`. On activate you should see six `0x07` frames, then `0x0D` per `write()` while driving. |
| `ros2 pkg list` missing the 4 packages | overlay not sourced — run through `pixi run --environment l4t …`, and confirm `install/` exists (build succeeded). |
| joystick does nothing, `/joy` silent | wrong `device_id` / not `/dev/input/js0`; check `ls /dev/input/js*` and `jstest`. Chain: `/joy` → `joy_tank_drive` → `/diff_drive_controller/cmd_vel_unstamped` (hold button 5). |
