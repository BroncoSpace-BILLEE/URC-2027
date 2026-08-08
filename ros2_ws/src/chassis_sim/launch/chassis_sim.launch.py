from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch_ros.parameter_descriptions import ParameterValue
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch.actions import TimerAction
from launch_ros.substitutions import FindPackageShare

import os
from ament_index_python.packages import get_package_share_directory
from launch.actions import SetEnvironmentVariable

desc_share = get_package_share_directory("chassis_description")  # .../share/chassis_description
share_root = os.path.dirname(desc_share)                         # .../share

set_env = [
    SetEnvironmentVariable("IGN_GAZEBO_MODEL_PATH", share_root),
    SetEnvironmentVariable("IGN_GAZEBO_RESOURCE_PATH", share_root),
    # Also set newer names (harmless on Fortress)
    SetEnvironmentVariable("GZ_SIM_MODEL_PATH", share_root),
    SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH", share_root),
]

def generate_launch_description():
    # --- Launch arguments ---
    description_pkg = LaunchConfiguration("description_pkg")
    xacro_file = LaunchConfiguration("xacro_file")
    entity_name = LaunchConfiguration("entity_name")

    # Pass-through argument to ros_gz_sim's gz_sim.launch.py
    # Examples:
    #   "empty.sdf"
    #   "-r -v 4 empty.sdf"
    #   "-r -v 4 /absolute/path/to/world.sdf"
    gz_args = LaunchConfiguration("gz_args")

    x = LaunchConfiguration("x")
    y = LaunchConfiguration("y")
    z = LaunchConfiguration("z")
    yaw = LaunchConfiguration("yaw")

    declare_args = [
        DeclareLaunchArgument(
            "description_pkg",
            default_value="chassis_description",
            description="Package that contains the robot URDF/Xacro in its share/ directory.",
        ),
        DeclareLaunchArgument(
            "xacro_file",
            default_value="urdf/chassis_model.xacro",
            description="Path to the robot Xacro (relative to the description package share).",
        ),
        DeclareLaunchArgument(
            "entity_name",
            default_value="chassis",
            description="Name of the spawned entity in Gazebo.",
        ),
        DeclareLaunchArgument(
            "gz_args",
            default_value="-r -v 4 empty.sdf",
            description="Arguments passed to Gazebo Sim (via ros_gz_sim gz_sim.launch.py).",
        ),
        DeclareLaunchArgument("x", default_value="0.0", description="Spawn X (m)."),
        DeclareLaunchArgument("y", default_value="0.0", description="Spawn Y (m)."),
        DeclareLaunchArgument("z", default_value="0.2", description="Spawn Z (m)."),
        DeclareLaunchArgument("yaw", default_value="0.0", description="Spawn yaw (rad)."),
    ]
    xacro_path = PathJoinSubstitution([
    FindPackageShare(description_pkg),
    xacro_file,
    ])

    # --- Build robot_description from Xacro ---

    controllers_yaml = PathJoinSubstitution([
        FindPackageShare("chassis_sim"),
        "config",
        "controllers.yaml",
    ])

    robot_description = ParameterValue(
    Command([
        "xacro", " ",
        xacro_path, " ",
        "controllers_yaml:=", controllers_yaml
    ]),
    value_type=str,
    )

    # --- Launch Gazebo Sim using ros_gz_sim's included launch file ---
    gz_sim_launch = IncludeLaunchDescription(
    PythonLaunchDescriptionSource(
        PathJoinSubstitution([
            FindPackageShare("ros_gz_sim"),
            "launch",
            "gz_sim.launch.py"
        ])
    ),
    launch_arguments={
        "gz_args": gz_args,
        "on_exit_shutdown": "true",
    }.items(),
    )

    # Optional: help Gazebo find resources (meshes, worlds, etc.) via GZ_SIM_RESOURCE_PATH
    # This appends your description package share directory to the resource path.
    set_resource_path = SetEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH",
        value=PathJoinSubstitution([FindPackageShare(description_pkg)]),
    )

    # --- Publish TF and robot_description ---
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[{"robot_description": robot_description, "use_sim_time": True}],
    )

    # --- Bridge /clock so ROS nodes use simulation time (critical for controllers / Nav2) ---
    clock_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        output="screen",
    )

    # --- Spawn the robot from /robot_description into Gazebo ---
    spawn_entity = Node(
        package="ros_gz_sim",
        executable="create",
        output="screen",
        arguments=[
            "-name", entity_name,
            "-topic", "robot_description",
            "-x", x, "-y", y, "-z", z,
            "-Y", yaw,
        ],
    )

    spawn_jsb = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_state_broadcaster", "--controller-manager", "/controller_manager"],
        output="screen",
    )

    spawn_diff = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["diff_drive_controller", "--controller-manager", "/controller_manager"],
        output="screen",
    )   

    spawn_controllers = TimerAction(
        period=3.0,
        actions=[spawn_jsb, spawn_diff],
    )

 


    return LaunchDescription(
        declare_args
        + set_env
        + [
            set_resource_path,
            gz_sim_launch,
            clock_bridge,
            robot_state_publisher,
            spawn_entity,
            spawn_controllers,
        ]
    )
