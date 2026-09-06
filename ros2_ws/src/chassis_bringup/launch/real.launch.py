"""Real-hardware drivetrain bring-up (no Gazebo).

Parallel to sim_gz.launch.py: same robot_description, same controllers.yaml, same
diff_drive_controller + joint_state_broadcaster. The only difference is the
ros2_control backend — this expands the URDF with use_sim:=false so the
OdescSystemHardware SocketCAN plugin is loaded instead of ign_ros2_control, and
it starts a standalone controller_manager (ros2_control_node) rather than letting
Gazebo host it.

    ros2 launch chassis_bringup real.launch.py
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

declare_args = [
    DeclareLaunchArgument(
        "description_pkg",
        default_value="robot_description",
        description="Package that contains the robot URDF/Xacro in its share/ directory.",
    ),
    DeclareLaunchArgument(
        "xacro_file",
        default_value="urdf/robot.urdf.xacro",
        description="Path to the robot Xacro (relative to the description package share).",
    ),
    DeclareLaunchArgument(
        "controllers_file",
        default_value="config/controllers.yaml",
        description="ros2_control controller config (relative to the description package share). "
        "Shared verbatim with sim_gz.launch.py.",
    ),
]


def generate_launch_description():
    description_pkg = LaunchConfiguration("description_pkg")
    xacro_file = LaunchConfiguration("xacro_file")
    controllers_file = LaunchConfiguration("controllers_file")

    xacro_path = PathJoinSubstitution([FindPackageShare(description_pkg), xacro_file])
    controllers_path = PathJoinSubstitution(
        [FindPackageShare(description_pkg), controllers_file]
    )

    # use_sim:=false -> ros2_control.urdf.xacro loads odesc/OdescSystemHardware.
    robot_description = ParameterValue(
        Command(["xacro", " ", xacro_path, " ", "use_sim:=false"]),
        value_type=str,
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[{"robot_description": robot_description, "use_sim_time": False}],
    )

    # Standalone controller_manager. controllers.yaml carries use_sim_time: true
    # for the Gazebo path; override it to false here without editing the file.
    controller_manager = Node(
        package="controller_manager",
        executable="ros2_control_node",
        output="screen",
        parameters=[
            {"robot_description": robot_description},
            controllers_path,
            {"use_sim_time": False},
        ],
    )

    # Same spawner invocation as sim_gz.launch.py.
    controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["diff_drive_controller", "joint_state_broadcaster"],
    )

    return LaunchDescription(
        declare_args
        + [
            robot_state_publisher,
            controller_manager,
            controller_spawner,
        ]
    )
