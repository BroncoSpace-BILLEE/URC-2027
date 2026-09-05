# teleop / joy_tank_drive

## 1. How This Node Works

The `teleop` package turns a USB joystick into rover drive commands. Its launch file starts the ROS 2 `joy` driver, which reads the selected Linux joystick device and publishes `sensor_msgs/msg/Joy` messages on `/joy`. It also starts this package's `joy_tank_drive` executable, named `joy_tank_drive` at launch.

`joy_tank_drive` reads one axis for the left side of the controller and one for the right side. While the configured safety button is held, it averages the two values for forward/reverse velocity and uses their difference for yaw. It publishes a `geometry_msgs/msg/Twist` for every received joystick message; when the safety button is not pressed, that message is all zeroes. The launch remaps its `/cmd_vel` output to `/diff_drive_controller/cmd_vel_unstamped`, the unstamped velocity input expected by the workspace's diff-drive controller.

The package is event-driven: joystick messages trigger the conversion immediately, rather than a timer continuously republishing a command. The supplied `joy` configuration enables a 20 Hz autorepeat rate, so a connected joystick continues to deliver its most recent state and therefore continues to refresh a held command.

## 2. Technologies Behind It

- **ROS distro:** ROS 2 Humble, as configured by `ros2_ws/pixi.toml`.
- **Language(s) / core libraries:** C++ with `rclcpp`; `sensor_msgs/msg/Joy` input and `geometry_msgs/msg/Twist` output.
- **External dependencies:** The ROS 2 `joy` package and a joystick exposed by Linux (normally under `/dev/input`). No vendor SDK or custom hardware driver is used here.
- **Build system / target platform(s):** `ament_cmake` and `colcon`; this repository provides a Pixi environment for the ROS desktop workspace. The node is portable ROS 2 C++ and is intended to command the rover's `diff_drive_controller`.
- **Middleware / networking notes:** The code uses default ROS 2 communication settings with depth-1 queues for both `/joy` and `/cmd_vel`. It has no bridge, DDS-vendor, or network-specific configuration.

## 3. How It Was Written

The package keeps joystick hardware access and rover-specific drive mixing separate. `joy_node` is responsible for device selection, deadzone handling, and message publication; `JoyTankDrive` in [`src/joy_teleop.cpp`](src/joy_teleop.cpp) only maps the generic `Joy` message to a rover velocity command. This lets joystick tuning remain in [`config/joystick.yaml`](config/joystick.yaml) while retaining a small custom control node.

The conversion in `JoyTankDrive::topic_callback` implements a simple differential-drive mix: `linear.x = (left + right) / 2 * max_vel` and `angular.z = (right - left) / 2 * max_vel`. Holding the safety button gates both values; releasing it publishes a zero `Twist`. All other linear and angular components are explicitly left at zero. The launch-level output remap keeps the executable's generic `/cmd_vel` interface while connecting it to this rover's controller.

No package-specific unit tests or hardware-in-the-loop tests are defined in the source. Validate changes with a connected controller by inspecting `/joy` and `/diff_drive_controller/cmd_vel_unstamped` before enabling the rover drivetrain.

**Known limitations / TODO**

- `config/joystick.yaml` sets `left_axis`, `right_axis`, and `max_vel`, but does not set `safety_button`; the node therefore uses its code default of button index `5`. Set it explicitly for each controller layout.
- The callback indexes `msg.axes` and `msg.buttons` directly. Invalid axis/button indices for the connected joystick can cause an out-of-range access; verify the controller layout with `/joy` before changing mappings.
- The package's `package.xml` does not currently declare its runtime/build dependencies (`rclcpp`, messages, or `joy`), even though `CMakeLists.txt` finds the C++ dependencies and the launch file requires `joy`.
- The current Gazebo bringup documentation notes that its active bridge does not connect velocity commands to Gazebo, so this launch alone will not make the simulated rover move.

## 4. Architecture

### 4a. Node composition

```mermaid
graph TD
    L[teleop.launch.py] --> J[joy_node\npackage: joy]
    L --> T[joy_tank_drive\npackage: teleop]
    J -->|/joy\nsensor_msgs/msg/Joy| T
    T -->|/cmd_vel remapped to\n/diff_drive_controller/cmd_vel_unstamped\ngeometry_msgs/msg/Twist| D[diff_drive_controller]
```

### 4b. Topic / interface graph

```mermaid
graph LR
    H[USB joystick] --> J[joy_node]
    J -->|/joy\nsensor_msgs/msg/Joy| T[joy_tank_drive]
    T -->|/diff_drive_controller/cmd_vel_unstamped\ngeometry_msgs/msg/Twist| D[diff_drive_controller]
```

## 5. How to Run It

### Prerequisites

- A ROS 2 Humble environment or the repository's Pixi environment.
- A joystick recognized by the host operating system. The supplied configuration selects `device_id: 0`.
- A running `diff_drive_controller` that accepts unstamped velocity commands on `/diff_drive_controller/cmd_vel_unstamped` if rover motion is required.
- Keep the rover safely supported or its drive power disabled while checking the mappings for a new controller.

### Build

From the ROS workspace:

```bash
cd ros2_ws
pixi run colcon build --packages-select teleop
source install/setup.bash
```

If using a separately installed ROS 2 Humble environment, run the equivalent `colcon build --packages-select teleop` after sourcing the Humble setup script.

### Launch

```bash
cd ros2_ws
source install/setup.bash
ros2 launch teleop teleop.launch.py
```

The launch reads `config/joystick.yaml`. The checked-in mapping is joystick device `0`, deadzone `0.05`, autorepeat rate `20.0 Hz`, left axis `1`, right axis `4`, and `max_vel` `2.0`. The safety button remains the executable default: index `5`.

### Verify it's running

1. Confirm both processes are present:

   ```bash
   ros2 node list
   ```

   Expected entries include `/joy_node` and `/joy_tank_drive`.

2. Move the sticks and inspect the raw input:

   ```bash
   ros2 topic echo /joy
   ```

3. In another terminal, hold safety button index `5` and verify the generated command:

   ```bash
   ros2 topic echo /diff_drive_controller/cmd_vel_unstamped
   ```

   With the safety button released, each published `Twist` should contain zero velocity. With it held, only `linear.x` and `angular.z` should be nonzero.

### Common issues

- **No `/joy` messages:** make sure the joystick is connected, is visible to the host, and is the device selected by `device_id: 0`; choose a different `device_id` in `config/joystick.yaml` when needed.
- **No drive command while moving the sticks:** hold safety button index `5`, or add the controller's intended `safety_button` index to the `joy_tank_drive` parameters in `config/joystick.yaml`.
- **Unexpected steering or speed:** inspect `/joy`, then update `left_axis`, `right_axis`, or `max_vel` to match the physical controller.
- **Commands appear but the rover does not move:** start and configure the `diff_drive_controller`; its command topic must be `/diff_drive_controller/cmd_vel_unstamped`. For the repository's current Gazebo launch, a velocity bridge is still required.

## 6. Subnode Breakdown

### `joy_node`

- **Package:** `joy`
- **Purpose:** Reads the configured Linux joystick device, applies input preprocessing, and emits ROS 2 joystick messages.
- **Publishes:**

  | Topic | Type | Description |
  |---|---|---|
  | `/joy` | `sensor_msgs/msg/Joy` | Axis values and button states from the joystick. |

- **Subscribes:** None declared by this launch.
- **Services / Actions:** No services or actions are declared by this package's launch.
- **Parameters:**

  | Name | Launch value | Description |
  |---|---:|---|
  | `device_id` | `0` | Linux joystick device index to open. |
  | `deadzone` | `0.05` | Input magnitude treated as centered. |
  | `autorepeat_rate` | `20.0` | Rate in Hz for republishing the latest joystick state. |

- **Depends on:** A joystick device available to the operating system.

### `joy_tank_drive`

- **Package:** `teleop`
- **Purpose:** Converts left/right joystick axes to a gated differential-drive velocity command.
- **Publishes:**

  | Topic | Type | Description |
  |---|---|---|
  | `/cmd_vel` (remapped to `/diff_drive_controller/cmd_vel_unstamped`) | `geometry_msgs/msg/Twist` | Forward/reverse command in `linear.x` and turn command in `angular.z`. |

- **Subscribes:**

  | Topic | Type | Description |
  |---|---|---|
  | `/joy` | `sensor_msgs/msg/Joy` | Raw axes and button state from `joy_node`. |

- **Services / Actions:** No custom services or actions.
- **Parameters:**

  | Name | Code default | Launch value | Description |
  |---|---:|---:|---|
  | `left_axis` | `0` | `1` | Index of the left drive axis. |
  | `right_axis` | `2` | `4` | Index of the right drive axis. |
  | `safety_button` | `5` | not set | Button index that must be nonzero to send motion. |
  | `max_vel` | `0.0` | `2.0` | Multiplier applied to both mixed velocity values. |

- **Depends on:** `joy_node` publishing valid `/joy` messages and a consumer, typically `diff_drive_controller`, subscribed to the remapped command topic.
