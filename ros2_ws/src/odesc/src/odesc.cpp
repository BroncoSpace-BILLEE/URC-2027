// odesc.cpp — implementation of OdescSystemHardware.
//
// See odesc.hpp for the high-level description. The SocketCAN parts are
// Linux-only; on other platforms (e.g. a Mac dev build of the workspace) the
// class still compiles and registers, but on_activate() fails cleanly instead
// of touching a CAN socket that cannot exist.

#include "odesc/odesc.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <string>

#include "odesc/constants.hpp"
#include "hardware_interface/types/hardware_interface_type_values.hpp"
#include "pluginlib/class_list_macros.hpp"
#include "rclcpp/rclcpp.hpp"

#if defined(__linux__)
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>
#include <poll.h>
#include <cerrno>

#include <linux/can.h>
#include <linux/can/raw.h>
#endif

namespace
{
constexpr const char * kLogger = "OdescSystemHardware";

// ODrive axis states (CANSimple payload for Set_Axis_Requested_State, 0x07).
// These are NOT in constants.hpp (which only carries command IDs), so they are
// defined here against ODrive firmware v0.5.x.
constexpr uint32_t kAxisStateIdle = 1;
constexpr uint32_t kAxisStateClosedLoopControl = 8;

constexpr double kTwoPi = 2.0 * M_PI;
}  // namespace

namespace odesc
{

hardware_interface::CallbackReturn OdescSystemHardware::on_init(
  const hardware_interface::HardwareInfo & info)
{
  if (hardware_interface::SystemInterface::on_init(info) !=
    hardware_interface::CallbackReturn::SUCCESS)
  {
    return hardware_interface::CallbackReturn::ERROR;
  }

  // ---- hardware-level parameters ----
  if (info_.hardware_parameters.count("can_interface")) {
    can_interface_ = info_.hardware_parameters.at("can_interface");
  } else {
    RCLCPP_WARN(
      rclcpp::get_logger(kLogger),
      "no 'can_interface' hardware param set; defaulting to '%s' — this is UNCONFIRMED "
      "against the actual Jetson/USB-CAN enumeration, verify before relying on it.",
      can_interface_.c_str());
  }

  if (info_.hardware_parameters.count("gear_ratio")) {
    gear_ratio_ = std::stod(info_.hardware_parameters.at("gear_ratio"));
  } else {
    RCLCPP_WARN(
      rclcpp::get_logger(kLogger),
      "no 'gear_ratio' hardware param set; defaulting to %.3f — this is a PLACEHOLDER "
      "not confirmed against the physical gearbox (see odesc/config/node_map.yaml).",
      gear_ratio_);
  }

  if (gear_ratio_ == 0.0 || !std::isfinite(gear_ratio_)) {
    RCLCPP_FATAL(
      rclcpp::get_logger(kLogger), "gear_ratio must be a non-zero finite number, got %f",
      gear_ratio_);
    return hardware_interface::CallbackReturn::ERROR;
  }

  // ---- per-joint parameters + interface sanity ----
  const size_t n = info_.joints.size();
  joint_names_.reserve(n);
  node_ids_.reserve(n);

  for (const auto & joint : info_.joints) {
    if (joint.command_interfaces.size() != 1 ||
      joint.command_interfaces[0].name != hardware_interface::HW_IF_VELOCITY)
    {
      RCLCPP_FATAL(
        rclcpp::get_logger(kLogger),
        "joint '%s' must have exactly one '%s' command interface.",
        joint.name.c_str(), hardware_interface::HW_IF_VELOCITY);
      return hardware_interface::CallbackReturn::ERROR;
    }

    bool has_pos = false, has_vel = false;
    for (const auto & si : joint.state_interfaces) {
      has_pos |= (si.name == hardware_interface::HW_IF_POSITION);
      has_vel |= (si.name == hardware_interface::HW_IF_VELOCITY);
    }
    if (!has_pos || !has_vel) {
      RCLCPP_FATAL(
        rclcpp::get_logger(kLogger),
        "joint '%s' must expose both 'position' and 'velocity' state interfaces.",
        joint.name.c_str());
      return hardware_interface::CallbackReturn::ERROR;
    }

    auto nid_it = joint.parameters.find("node_id");
    if (nid_it == joint.parameters.end()) {
      RCLCPP_FATAL(
        rclcpp::get_logger(kLogger),
        "joint '%s' is missing the required <param name=\"node_id\"> "
        "(canonical map: odesc/config/node_map.yaml).",
        joint.name.c_str());
      return hardware_interface::CallbackReturn::ERROR;
    }

    const int nid = std::stoi(nid_it->second);
    if (nid < 0 || nid > static_cast<int>(odrive_can::kMaxNodeId)) {
      RCLCPP_FATAL(
        rclcpp::get_logger(kLogger), "joint '%s' node_id %d out of range [0, %d].",
        joint.name.c_str(), nid, static_cast<int>(odrive_can::kMaxNodeId));
      return hardware_interface::CallbackReturn::ERROR;
    }

    joint_names_.push_back(joint.name);
    node_ids_.push_back(static_cast<uint8_t>(nid));
  }

  hw_positions_.assign(n, 0.0);
  hw_velocities_.assign(n, 0.0);
  hw_commands_.assign(n, 0.0);

  RCLCPP_INFO(
    rclcpp::get_logger(kLogger),
    "initialised %zu joints on CAN interface '%s', gear_ratio=%.3f.",
    n, can_interface_.c_str(), gear_ratio_);

  return hardware_interface::CallbackReturn::SUCCESS;
}

std::vector<hardware_interface::StateInterface> OdescSystemHardware::export_state_interfaces()
{
  std::vector<hardware_interface::StateInterface> ifaces;
  for (size_t i = 0; i < joint_names_.size(); ++i) {
    ifaces.emplace_back(
      joint_names_[i], hardware_interface::HW_IF_POSITION, &hw_positions_[i]);
    ifaces.emplace_back(
      joint_names_[i], hardware_interface::HW_IF_VELOCITY, &hw_velocities_[i]);
  }
  return ifaces;
}

std::vector<hardware_interface::CommandInterface> OdescSystemHardware::export_command_interfaces()
{
  std::vector<hardware_interface::CommandInterface> ifaces;
  for (size_t i = 0; i < joint_names_.size(); ++i) {
    ifaces.emplace_back(
      joint_names_[i], hardware_interface::HW_IF_VELOCITY, &hw_commands_[i]);
  }
  return ifaces;
}

hardware_interface::CallbackReturn OdescSystemHardware::on_activate(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
#if defined(__linux__)
  can_fd_ = ::socket(PF_CAN, SOCK_RAW, CAN_RAW);
  if (can_fd_ < 0) {
    RCLCPP_FATAL(
      rclcpp::get_logger(kLogger), "socket(PF_CAN) failed: %s", std::strerror(errno));
    return hardware_interface::CallbackReturn::ERROR;
  }

  struct ifreq ifr{};
  std::strncpy(ifr.ifr_name, can_interface_.c_str(), IFNAMSIZ - 1);
  if (::ioctl(can_fd_, SIOCGIFINDEX, &ifr) < 0) {
    RCLCPP_FATAL(
      rclcpp::get_logger(kLogger), "CAN interface '%s' not found: %s",
      can_interface_.c_str(), std::strerror(errno));
    ::close(can_fd_);
    can_fd_ = -1;
    return hardware_interface::CallbackReturn::ERROR;
  }

  struct sockaddr_can addr{};
  addr.can_family = AF_CAN;
  addr.can_ifindex = ifr.ifr_ifindex;
  if (::bind(can_fd_, reinterpret_cast<struct sockaddr *>(&addr), sizeof(addr)) < 0) {
    RCLCPP_FATAL(
      rclcpp::get_logger(kLogger), "bind(%s) failed: %s",
      can_interface_.c_str(), std::strerror(errno));
    ::close(can_fd_);
    can_fd_ = -1;
    return hardware_interface::CallbackReturn::ERROR;
  }

  {
    std::lock_guard<std::mutex> lk(est_mutex_);
    est_.fill(Estimate{});
  }
  std::fill(hw_commands_.begin(), hw_commands_.end(), 0.0);

  rx_running_ = true;
  rx_thread_ = std::thread(&OdescSystemHardware::rx_loop, this);

  request_axis_state_all(kAxisStateClosedLoopControl);

  RCLCPP_INFO(
    rclcpp::get_logger(kLogger), "activated on '%s'; %zu nodes set to CLOSED_LOOP_CONTROL.",
    can_interface_.c_str(), node_ids_.size());
  return hardware_interface::CallbackReturn::SUCCESS;
#else
  RCLCPP_FATAL(
    rclcpp::get_logger(kLogger),
    "OdescSystemHardware needs Linux SocketCAN; this build is not Linux. "
    "Use the Gazebo (use_sim:=true) backend on this platform.");
  return hardware_interface::CallbackReturn::ERROR;
#endif
}

hardware_interface::CallbackReturn OdescSystemHardware::on_deactivate(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
#if defined(__linux__)
  if (can_fd_ >= 0) {
    request_axis_state_all(kAxisStateIdle);
  }

  rx_running_ = false;
  if (rx_thread_.joinable()) {
    rx_thread_.join();
  }

  if (can_fd_ >= 0) {
    ::close(can_fd_);
    can_fd_ = -1;
  }
  RCLCPP_INFO(rclcpp::get_logger(kLogger), "deactivated; all nodes set to IDLE.");
#endif
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn OdescSystemHardware::on_cleanup(
  const rclcpp_lifecycle::State & previous_state)
{
  return on_deactivate(previous_state);
}

hardware_interface::CallbackReturn OdescSystemHardware::on_shutdown(
  const rclcpp_lifecycle::State & previous_state)
{
  return on_deactivate(previous_state);
}

hardware_interface::return_type OdescSystemHardware::read(
  const rclcpp::Time & /*time*/, const rclcpp::Duration & /*period*/)
{
  std::lock_guard<std::mutex> lk(est_mutex_);
  for (size_t i = 0; i < joint_names_.size(); ++i) {
    const Estimate & e = est_[node_ids_[i]];
    // motor-shaft turns -> wheel-joint radians. Left/right mirroring is handled
    // by diff_drive_controller's wheel lists, NOT here — do not add a per-side
    // sign flip without a bench measurement that proves the ODESC reports the
    // physically-mirrored sign.
    hw_positions_[i] = e.pos_turns * kTwoPi / gear_ratio_;
    hw_velocities_[i] = e.vel_turns_s * kTwoPi / gear_ratio_;
  }
  return hardware_interface::return_type::OK;
}

hardware_interface::return_type OdescSystemHardware::write(
  const rclcpp::Time & /*time*/, const rclcpp::Duration & /*period*/)
{
  if (can_fd_ < 0) {
    return hardware_interface::return_type::ERROR;
  }

  for (size_t i = 0; i < joint_names_.size(); ++i) {
    // wheel-joint rad/s -> motor-shaft turns/s (inverse of read()).
    const double motor_turns_s = hw_commands_[i] * gear_ratio_ / kTwoPi;
    const float vel = static_cast<float>(motor_turns_s);

    uint8_t payload[8] = {0};            // [0:4] Input_Vel, [4:8] Input_Torque_FF = 0
    std::memcpy(payload, &vel, sizeof(vel));
    send_frame(node_ids_[i], odrive_can::MSG_SET_INPUT_VEL, payload, sizeof(payload));
  }
  return hardware_interface::return_type::OK;
}

bool OdescSystemHardware::send_frame(
  uint8_t node_id, uint8_t cmd_id, const uint8_t * payload, uint8_t len)
{
#if defined(__linux__)
  if (can_fd_ < 0 || len > 8) {
    return false;
  }
  struct can_frame frame{};
  frame.can_id = odrive_can::MakeArbitrationId(node_id, cmd_id) & CAN_SFF_MASK;
  frame.can_dlc = len;
  if (len > 0 && payload != nullptr) {
    std::memcpy(frame.data, payload, len);
  }
  const ssize_t n = ::write(can_fd_, &frame, sizeof(frame));
  if (n != static_cast<ssize_t>(sizeof(frame))) {
    static rclcpp::Clock s_clock{RCL_STEADY_TIME};
    RCLCPP_WARN_THROTTLE(
      rclcpp::get_logger(kLogger), s_clock, 1000,
      "CAN write to node %d (cmd 0x%02X) failed: %s",
      static_cast<int>(node_id), static_cast<unsigned>(cmd_id), std::strerror(errno));
    return false;
  }
  return true;
#else
  (void)node_id;
  (void)cmd_id;
  (void)payload;
  (void)len;
  return false;
#endif
}

void OdescSystemHardware::request_axis_state_all(uint32_t axis_state)
{
  uint8_t payload[4] = {0};
  std::memcpy(payload, &axis_state, sizeof(axis_state));
  for (uint8_t nid : node_ids_) {
    send_frame(nid, odrive_can::MSG_SET_AXIS_REQUESTED_STATE, payload, sizeof(payload));
  }
}

void OdescSystemHardware::rx_loop()
{
#if defined(__linux__)
  while (rx_running_.load()) {
    struct pollfd pfd{};
    pfd.fd = can_fd_;
    pfd.events = POLLIN;

    const int pr = ::poll(&pfd, 1, 100);  // 100 ms so we re-check rx_running_
    if (pr <= 0) {
      continue;  // timeout (0) or interrupted (-1/EINTR)
    }
    if (!(pfd.revents & POLLIN)) {
      continue;
    }

    struct can_frame frame{};
    const ssize_t n = ::read(can_fd_, &frame, sizeof(frame));
    if (n < static_cast<ssize_t>(sizeof(frame))) {
      continue;
    }

    const uint32_t id = frame.can_id & CAN_SFF_MASK;
    const uint8_t node_id = static_cast<uint8_t>((id >> odrive_can::kCommandIdBits) & 0x3F);
    const uint8_t cmd = static_cast<uint8_t>(id & 0x1F);

    if (cmd == odrive_can::MSG_GET_ENCODER_ESTIMATES && frame.can_dlc >= 8) {
      float pos = 0.0f, vel = 0.0f;
      std::memcpy(&pos, frame.data, sizeof(pos));          // LE float32, motor turns
      std::memcpy(&vel, frame.data + 4, sizeof(vel));      // LE float32, motor turns/s
      std::lock_guard<std::mutex> lk(est_mutex_);
      est_[node_id].pos_turns = static_cast<double>(pos);
      est_[node_id].vel_turns_s = static_cast<double>(vel);
    }
  }
#endif
}

}  // namespace odesc

PLUGINLIB_EXPORT_CLASS(odesc::OdescSystemHardware, hardware_interface::SystemInterface)
