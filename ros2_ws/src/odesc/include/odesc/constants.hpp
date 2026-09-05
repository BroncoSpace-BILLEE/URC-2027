// odrive_can_protocol.hpp
//
// Command (message) IDs for the ODrive "CAN Simple" protocol.
//
// Source: ODrive Documentation v0.5.4 - CAN Protocol - Messages
//   https://docs.odriverobotics.com/v/0.5.4/can-protocol.html#messages
// (transcribed directly from the page's "Download CAN Messages as csv" table)
//
// Frame layout:
//   11-bit arbitration ID = (node_id << 5) | cmd_id
//   node_id: bits [10:5]  (0x00 - 0x3F, 0x3F = unaddressed/broadcast)
//   cmd_id:  bits [4:0]   (0x00 - 0x1F)
//
// These messages are call & response: the Master sends a message with the
// RTR bit set, and the axis responds with the same ID and specified payload.
// All multi-byte values are little-endian.
//
#pragma once

#include <cstdint>

namespace odrive_can {

    // Command ID type (5 bits: 0x00 - 0x1F)
    using CommandId = std::uint8_t;

    // Number of bits used for the command ID portion of the 11-bit CAN ID.
    inline constexpr std::uint8_t kCommandIdBits = 5;

    // Max node ID (6 bits).
    inline constexpr std::uint8_t kMaxNodeId = 0x3F;

    // Node ID representing an unaddressed / broadcast ODrive.
    inline constexpr std::uint8_t kBroadcastNodeId = 0x3F;

    // Helper to build the 11-bit arbitration ID from a node ID and command ID.
    constexpr std::uint16_t MakeArbitrationId(std::uint8_t node_id, CommandId cmd_id) {
        return static_cast<std::uint16_t>((node_id << kCommandIdBits) | (cmd_id & 0x1F));
    }

    // ---------------------------------------------------------------------------
    // CAN Simple message / command IDs (firmware v0.5.4)
    // ---------------------------------------------------------------------------
    enum : CommandId {
        MSG_CO_NMT_CTRL              = 0x00, // CANOpen NMT Message ** (reserved, not used by CAN Simple)
        MSG_ODRIVE_HEARTBEAT         = 0x01, // ODrive Heartbeat Message
        MSG_ODRIVE_ESTOP             = 0x02, // ODrive Estop Message
        MSG_GET_MOTOR_ERROR          = 0x03, // Get Motor Error *
        MSG_GET_ENCODER_ERROR        = 0x04, // Get Encoder Error *
        MSG_GET_SENSORLESS_ERROR     = 0x05, // Get Sensorless Error *
        MSG_SET_AXIS_NODE_ID         = 0x06, // Set Axis Node ID
        MSG_SET_AXIS_REQUESTED_STATE = 0x07, // Set Axis Requested State
        MSG_SET_AXIS_STARTUP_CONFIG  = 0x08, // Set Axis Startup Config (not yet implemented)
        MSG_GET_ENCODER_ESTIMATES    = 0x09, // Get Encoder Estimates *
        MSG_GET_ENCODER_COUNT        = 0x0A, // Get Encoder Count *
        MSG_SET_CONTROLLER_MODES     = 0x0B, // Set Controller Modes
        MSG_SET_INPUT_POS            = 0x0C, // Set Input Pos
        MSG_SET_INPUT_VEL            = 0x0D, // Set Input Vel
        MSG_SET_INPUT_TORQUE         = 0x0E, // Set Input Torque
        MSG_SET_LIMITS               = 0x0F, // Set Limits
        MSG_START_ANTICOGGING        = 0x10, // Start Anticogging
        MSG_SET_TRAJ_VEL_LIMIT       = 0x11, // Set Traj Vel Limit
        MSG_SET_TRAJ_ACCEL_LIMITS    = 0x12, // Set Traj Accel Limits
        MSG_SET_TRAJ_INERTIA         = 0x13, // Set Traj Inertia
        MSG_GET_IQ                   = 0x14, // Get IQ *
        MSG_GET_SENSORLESS_ESTIMATES = 0x15, // Get Sensorless Estimates *
        MSG_REBOOT_ODRIVE            = 0x16, // Reboot ODrive ***
        MSG_GET_VBUS_VOLTAGE         = 0x17, // Get Bus Voltage and Current ***
        MSG_CLEAR_ERRORS             = 0x18, // Clear Errors
        MSG_SET_LINEAR_COUNT         = 0x19, // Set Linear Count
        MSG_SET_POSITION_GAIN        = 0x1A, // Set Position Gain
        MSG_SET_VEL_GAINS            = 0x1B, // Set Vel Gains
        MSG_GET_ADC_VOLTAGE          = 0x1C, // Get ADC Voltage **** (requires valid GPIO pin # in data byte 0)
        MSG_GET_CONTROLLER_ERROR     = 0x1D, // Get Controller Error *

        // 0x01E and 0x01F are not listed in the v0.5.4 messages table (unused).
    };

    // Full 11-bit CAN ID reserved for the CANOpen Heartbeat Message (**), listed
    // separately in the source table since it isn't part of the 5-bit cmd_id
    // space of any particular node: 0x700 (+ CANOpen node ID).
    inline constexpr std::uint16_t CO_HEARTBEAT_MESSAGE_ID = 0x700;

}  // namespace odrive_can