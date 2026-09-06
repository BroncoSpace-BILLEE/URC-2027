# B-003 Drivetrain + Teleop Sim — Live Checkpoint

**Branch:** `B-003-DrivetrainAndTeleopSim`  ·  **Repo:** `~/billee-software-2027`
**Owner of this pass:** Claude (session 2026-09-06, continuing the overnight `SETUP_STATUS.md` work)

> This file is updated as work progresses so it can be handed to the next agent
> without losing state. If the shell dies, resume from the last "DONE" item.
> Companion docs: `SETUP_STATUS.md` (Jetson host prep), `docs/RUN_GUIDE.md` (how to run).

---

## Objective for this pass (from the user, 2026-09-06)

1. RViz **and** Foxglove both usable as viewers. (DONE-ish before: Foxglove bridge dep only.)
2. Gamepad teleop visibly drives the robot in RViz.
3. Full CAN infrastructure: driver + bus bring-up + a no-hardware test path.
4. A way to run the sim in RViz when **no** ODESC/NEO motor controllers are present.
5. Full encoder-feedback → odometry → TF → viewer pipeline wired and verified.
6. Gear ratio set to **48:1** for the ODESC + NEO REV v1.1 motor (was a 64:1 placeholder).
7. Keep writing checkpoints (this file).
8. Everything compiles, launches, and runs.

---

## Status board

| # | Item | State |
|---|------|-------|
| 1 | Gear ratio 64 → 48 everywhere (code default, xacro, node_map, README) | DONE |
| 2 | `can_interface` / `gear_ratio` overridable from `real.launch.py` (xacro args) | DONE (xacro expands both ways OK) |
| 3 | `OdescSystemHardware` **mock mode** (`can_interface:=mock`, no CAN, full feedback loop) | DONE + verified |
| 4 | `tooling/can-up` (real `can0` @ 500k, plus `vcan0` test bus) + systemd unit | DONE (`tooling/can-up`, `tooling/can0.service`) |
| 5 | RViz config `chassis_bringup/rviz/drivetrain.rviz` + install rule | DONE |
| 6 | `chassis_bringup/launch/viz.launch.py` (rviz + foxglove_bridge) | DONE |
| 7 | `rviz:=` / `foxglove:=` opt-in args on `sim_gz.launch.py` and `real.launch.py` | DONE (default false → sim graph unchanged) |
| 8 | `docs/RUN_GUIDE.md` updated (bitrate 500k, mock/vcan rows, viz, use_sim_time box) | DONE |
| 9 | `odesc/README.md` updated (48:1, mock mode) | DONE |
| 10 | `pixi run --environment l4t build` clean | DONE (4/4, no warnings) |
| 11 | Sim smoke test (xvfb): controllers active, /joint_states, odom moves, TF | **DONE — PASS** (controllers active 2s, odom 0→(0.49,0.07) on drive, joint_states advance, /tf live, sim graph unchanged) |
| 12 | Mock real test: `real.launch.py can_interface:=mock` → odom moves on cmd_vel | **DONE — PASS** (hw active, both controllers active, odom 0→(1.15,0.77), TF odom→base_link live, joint_states advancing) |
| 13 | vcan test: `real.launch.py can_interface:=vcan0` | **DONE — PASS** — TX: 6× `Set_Axis_Requested_State` (0x07) on activate, 1650× `Set_Input_Vel` (0x0D) while driving, node IDs 0–5, arb id `(node<<5)\|cmd`. RX: injected `Get_Encoder_Estimates` (0x09) pos=2.0turn/vel=1.0tps → all joints read pos 0.26180 rad / vel 0.13090 rad/s = exactly `×2π/48`. |
| 14 | RViz loads the config headless without fatal error | **DONE — PASS** (rviz2 loads `drivetrain.rviz`, OpenGL 4.5, TF listener up, no parse errors) |
| 15 | Foxglove bridge launches on :8765 | **DONE — PASS** ("Server listening on port 8765", 0.0.0.0, advertises /tf /tf_static /robot_description /diff_drive_controller/odom) |
| 16 | README repo-architecture mermaid diagram (nodes/Foxglove/drivers/Gazebo/layers) | DONE (2 diagrams in `README.md` "Drivetrain architecture") |
| 17 | Teleop/gamepad chain (fake /joy → tank mix → cmd_vel → drivetrain) | **DONE — PASS** (held L+0.8/R+0.8 → lin.x 1.6; released → 0 deadman; L−0.6/R+0.6 → ang.z 1.2) |
| 18 | `tooling/can-up`: real `can0` up @ 500k + `vcan0` create/up | **DONE — PASS** (both brought up on the Jetson) |
| 19 | `docs/RUN_GUIDE.md` refreshed (500k, mock, vcan, viz, use_sim_time note) | DONE |

### EVERYTHING ON THE BOARD IS DONE + TESTED (2026-09-06). Nothing committed yet.

## ROOT CAUSE fixed this pass — standalone controller_manager hang

`real.launch.py` was letting `use_sim_time: true` (a Gazebo-ism baked into
`controllers.yaml`) reach the **standalone** `ros2_control_node`. With no `/clock`
publisher its RT update loop is frozen at t=0 and `load_controller` blocks forever
— every earlier "real" bring-up wedged at *"Loading controller
'diff_drive_controller'"*. Also seen: the `~/robot_description` **topic** path to
`ros2_control_node` is unreliable on this target (RT loop starves the executor
before the description arrives) — so the CM gets `robot_description` as a
**parameter**, and `SCHED_FIFO` failing ("Could not enable FIFO RT scheduling
policy") is only a warning, harmless once use_sim_time is false.

**Fix:** `real.launch.py` now writes a temp copy of `controllers.yaml` with
`controller_manager.use_sim_time: false` and hands the CM that (source file
untouched), and passes `robot_description` as a param. Verified working.
For real RT later: `tooling/can0.service`-style unit or `/etc/security/limits.d`
rtprio — not required for correctness, only for jitter.

## Key facts pinned down this pass

- Jetson has a **real `can0`** (Tegra `mttcan`) — this pass left it `UP @ 500 kbit/s`
  via `tooling/can-up can0`. `vcan` kernel module is present. `candump`/`cansend` installed.
- CAN bitrate is **500000** per `BILLEE_NEO_ODESC_Hardware_Integration_Guide.md`
  §3.4 (`odrv0.can.config.baud_rate = 500000`). The old `docs/RUN_GUIDE.md`
  said 1000000 — that was wrong, being corrected.
- `rviz2` is in the `l4t` pixi env; `foxglove_bridge` + its launch file are too.
- No `$DISPLAY` on the Jetson over SSH → GUI tools (`rviz2`, Gazebo GUI) run
  under `xvfb-run -a` for headless verification; real viewing is Foxglove from a
  laptop, or RViz on a machine with a display.

## How to resume / re-verify quickly

```bash
cd ~/billee-software-2027/ros2_ws && export PATH="$HOME/.pixi/bin:$PATH"
pixi run --environment l4t build
# sim:
xvfb-run -a pixi run --environment l4t ros2 launch chassis_bringup sim_gz.launch.py
# real, no hardware:
pixi run --environment l4t ros2 launch chassis_bringup real.launch.py can_interface:=mock
```

---

## Files changed this pass (all uncommitted, branch `B-003-DrivetrainAndTeleopSim`)

**New**
- `ros2_ws/src/chassis_bringup/launch/viz.launch.py` — RViz2 + foxglove_bridge, `rviz:=`/`foxglove:=`/`use_sim_time:=` args.
- `ros2_ws/src/chassis_bringup/rviz/drivetrain.rviz` — RobotModel + TF + `/diff_drive_controller/odom`, fixed frame `odom`.
- `tooling/can-up` — bring `can0` up @ 500 kbit/s / create+up `vcan0` / `down` / `status`.
- `tooling/can0.service` — systemd unit to persist `can0` @ 500k.
- `HANDOFF_CHECKPOINT.md` — this file.

**Modified**
- `ros2_ws/src/odesc/src/odesc.cpp` — **mock mode** (`can_interface` = `mock`/`none`): no socket, `read()` loops the command back through the 48:1 gear ratio + integrates position; `on_activate`/`on_deactivate`/`write` short-circuit. Warn text de-"PLACEHOLDER"-ed.
- `ros2_ws/src/odesc/include/odesc/odesc.hpp` — `gear_ratio_` default `48.0`, `mock_` flag, `mock_step()` decl.
- `ros2_ws/src/odesc/config/node_map.yaml` — `gear_ratio: 48.0` (+ rationale comment).
- `ros2_ws/src/odesc/README.md` — 48:1, mock-mode section, param table.
- `ros2_ws/src/robot_description/urdf/ros2_control.urdf.xacro` — `can_interface` + `gear_ratio` as `xacro:arg` (defaults `can0` / `48.0`), fed into `<hardware>`.
- `ros2_ws/src/chassis_bringup/launch/real.launch.py` — OpaqueFunction; writes a wall-clock (`use_sim_time: false`) temp copy of `controllers.yaml` (THE hang fix); `can_interface`/`gear_ratio`/`rviz`/`foxglove` launch args; includes `viz.launch.py`.
- `ros2_ws/src/chassis_bringup/launch/sim_gz.launch.py` — opt-in `rviz:=`/`foxglove:=` (default false → sim graph byte-identical), includes `viz.launch.py` with `use_sim_time:=true`.
- `ros2_ws/src/chassis_bringup/CMakeLists.txt` — install `rviz/`.
- `ros2_ws/src/chassis_bringup/package.xml` — `exec_depend` rviz2, foxglove_bridge.
- `README.md` — "Drivetrain architecture" section: 2 mermaid diagrams (layered node/topic/Foxglove/Gazebo dataflow + CAN frame layout).
- (pre-existing uncommitted from the overnight pass: `docker/Dockerfile.l4t-humble`, `pixi.toml/lock`, `sim_gz.launch.py` GUI-path fix, `README.md` L4T section, `SETUP_STATUS.md`, `docs/RUN_GUIDE.md`, `.devcontainer/l4t/`, `tooling/rover-ros2` — left as the overnight agent made them, only `docs/RUN_GUIDE.md` + `README.md` further edited.)

## To hand off cleanly (nothing is committed)

```bash
cd ~/billee-software-2027
git add -A
git commit -m "B-003: 48:1 gear ratio, OdescSystemHardware mock mode, viz.launch.py (RViz+Foxglove),
CAN tooling (can-up + can0.service), real.launch.py wall-clock fix, architecture docs

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push origin B-003-DrivetrainAndTeleopSim     # branch already tracks origin
```

## Verified this pass (Jetson Orin Nano, l4t pixi env, headless)

| Path | Result |
|---|---|
| `pixi run --environment l4t build` | 4/4 packages, no warnings/errors |
| xacro expand `use_sim:=true` | unchanged vs base (no node_id/can/gear in sim `<ros2_control>`) |
| xacro expand `use_sim:=false can_interface:=mock gear_ratio:=48.0` | correct `<hardware>` block |
| `sim_gz.launch.py` (xvfb) | controllers active 2 s; drive → odom 0→(0.49,0.07); `/joint_states`, `/tf` live |
| `real.launch.py can_interface:=mock` | hw `Robot` active; both controllers active; drive → odom 0→(1.15,0.77); `odom→base_link` TF live; `/joint_states` advancing |
| `real.launch.py can_interface:=vcan0` + `candump`/`cansend` | TX 0x07 ×6 on activate, 0x0D ×N while driving, node ids 0–5; RX 0x09 pos=2.0turn/vel=1.0tps → every wheel joint reads 0.26180 rad / 0.13090 rad/s = exactly `×2π/48` |
| `viz.launch.py` (xvfb) | `rviz2` loads `drivetrain.rviz` (OpenGL 4.5, no parse errors); `foxglove_bridge` "listening on port 8765" (0.0.0.0), advertises /tf,/tf_static,/robot_description,/odom |
| teleop chain (fake `/joy`) | held L+0.8/R+0.8 → `cmd_vel.linear.x` 1.6; **released → 0.0 (deadman)**; L−0.6/R+0.6 → `angular.z` 1.2 |
| `tooling/can-up` | `can0` UP @ 500 kbit/s (real Tegra `mttcan`), `vcan0` create/up/down |

## System state left changed (outside the repo)

- `can0` is **UP @ 500 kbit/s** (from `tooling/can-up can0`). Harmless with no ODESCs
  connected. `sudo ip link set can0 down` to revert, or install `tooling/can0.service`
  to make it permanent.
- `vcan0` test interface was deleted (not left behind).
- No `/etc/security/limits.d` RT changes were made (the classifier blocked the write).
  The standalone CM works without RT scheduling; only jitter suffers. If you want RRT:
  add `@realtime - rtprio 98` + `memlock unlimited` to `/etc/security/limits.d/99-realtime.conf`,
  `groupadd realtime`, `usermod -aG realtime $USER`, then re-login. (Do **not** `setcap`
  the conda `ros2_control_node` — it breaks `LD_LIBRARY_PATH` via AT_SECURE.)

## Not done / for the next agent

- Real ODESC bring-up (6 nodes, firmware per `BILLEE_NEO_ODESC_Hardware_Integration_Guide.md`) — still hardware-gated; §5 tests 2 & 4 need it.
- Confirm 48:1 against the physical gearbox (drive-a-known-distance bench test).
- Confirm `can0` really is the ODESC bus (vs a USB-CAN adapter enumerating as can1) once hardware is wired.
- `ros2_control_node` `~/robot_description` **topic** path is flaky on this box under the RT loop — `real.launch.py` passes `robot_description` as a **parameter** instead. Revisit if ros2_control is upgraded.
