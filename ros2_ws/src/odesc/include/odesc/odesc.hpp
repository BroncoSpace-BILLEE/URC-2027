// odesc.hpp
//
// ros2_control SystemInterface for the BILLEE drivetrain: six ODrive/ODESC
// motor controllers on a shared CAN bus, one per wheel joint, spoken to over a
// raw Linux SocketCAN socket (no extra ROS CAN dependency).
//
// This is the "real hardware" counterpart to the Gazebo ign_ros2_control plugin.
// diff_drive_controller does not know or care which one is loaded — it only ever
// sees wheel-joint position/velocity interfaces. The motor<->wheel gear-ratio
// conversion lives entirely in read()/write() here.
//
// CAN command subset used (see include/odesc/constants.hpp for the IDs):
//   0x07 Set_Axis_Requested_State  — CLOSED_LOOP_CONTROL on activate, IDLE on stop
//   0x09 Get_Encoder_Estimates     — cyclic RX: two LE float32 = pos/vel in motor turns
//   0x0D Set_Input_Vel             — TX per cycle: commanded motor turns/s
//
#pragma once

#include <array>
#include <atomic>
#include <cstdint>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "hardware_interface/handle.hpp"
#include "hardware_interface/hardware_info.hpp"
#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "rclcpp/duration.hpp"
#include "rclcpp/macros.hpp"
#include "rclcpp/time.hpp"
#include "rclcpp_lifecycle/state.hpp"

namespace odesc
{

class OdescSystemHardware : public hardware_interface::SystemInterface
{
public:
  RCLCPP_SHARED_PTR_DEFINITIONS(OdescSystemHardware)

  hardware_interface::CallbackReturn on_init(
    const hardware_interface::HardwareInfo & info) override;

  hardware_interface::CallbackReturn on_activate(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::CallbackReturn on_deactivate(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::CallbackReturn on_cleanup(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::CallbackReturn on_shutdown(
    const rclcpp_lifecycle::State & previous_state) override;

  std::vector<hardware_interface::StateInterface> export_state_interfaces() override;

  std::vector<hardware_interface::CommandInterface> export_command_interfaces() override;

  hardware_interface::return_type read(
    const rclcpp::Time & time, const rclcpp::Duration & period) override;

  hardware_interface::return_type write(
    const rclcpp::Time & time, const rclcpp::Duration & period) override;

private:
  // Latest encoder estimate for one node, in motor-shaft units, as reported by
  // Get_Encoder_Estimates (0x09). Written by the RX thread, read by read().
  struct Estimate
  {
    double pos_turns{0.0};
    double vel_turns_s{0.0};
  };

  // Build + send an 8-byte CAN data frame to <node_id> with command <cmd_id>.
  // Returns false on a socket write error. len bytes of payload are sent (0..8).
  bool send_frame(uint8_t node_id, uint8_t cmd_id, const uint8_t * payload, uint8_t len);

  // Send Set_Axis_Requested_State (0x07) with the given axis state to every node.
  void request_axis_state_all(uint32_t axis_state);

  // Blocking SocketCAN RX loop; runs on rx_thread_ while rx_running_ is true.
  void rx_loop();

  // ---- configuration (from the URDF <ros2_control> block) ----
  std::string can_interface_{"can0"};
  double gear_ratio_{64.0};
  std::vector<std::string> joint_names_;
  std::vector<uint8_t> node_ids_;

  // ---- ros2_control interface storage (indexed by joint) ----
  std::vector<double> hw_positions_;
  std::vector<double> hw_velocities_;
  std::vector<double> hw_commands_;

  // ---- SocketCAN ----
  int can_fd_{-1};
  std::thread rx_thread_;
  std::atomic<bool> rx_running_{false};

  // Latest estimate per CAN node ID (0x00-0x3F). Guarded by est_mutex_.
  std::mutex est_mutex_;
  std::array<Estimate, 64> est_{};
};

}  // namespace odesc
