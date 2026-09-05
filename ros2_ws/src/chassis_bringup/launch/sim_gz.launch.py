from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch_ros.parameter_descriptions import ParameterValue
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch.actions import OpaqueFunction
from launch_ros.substitutions import FindPackageShare

import os
from ament_index_python.packages import get_package_prefix, get_package_share_directory

desc_share = get_package_share_directory("robot_description")  
share_root = os.path.dirname(desc_share)                         
ign_ros2_control_plugin_path = os.path.join(
    get_package_prefix("ign_ros2_control"), "lib"
)

# environment variables required for GZ to render models properly
set_env = [
    SetEnvironmentVariable("IGN_GAZEBO_MODEL_PATH", share_root),
    SetEnvironmentVariable("IGN_GAZEBO_RESOURCE_PATH", share_root),
    SetEnvironmentVariable("GZ_SIM_MODEL_PATH", share_root),
    SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH", share_root),
    # Ignition Gazebo loads model system plugins from this path.  The control
    # plugin is supplied by the Pixi / ROS environment, not this workspace.
    SetEnvironmentVariable(
        "IGN_GAZEBO_SYSTEM_PLUGIN_PATH", ign_ros2_control_plugin_path
    ),
    SetEnvironmentVariable(
        "IGN_GUI_PLUGIN_PATH", 
        "/workspaces/URC-2027/ros2_ws/.pixi/envs/default/lib/ign-gazebo-6/plugins/gui"
    ),
    SetEnvironmentVariable(
        "QML2_IMPORT_PATH",
        "/workspaces/URC-2027/ros2_ws/.pixi/envs/default/lib/ign-gazebo-6/plugins/gui",
    ),

]

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
            "world_file",
            default_value="empty.sdf",
            description="Path to the robot world file (relative to the description package share).",
        ),
        DeclareLaunchArgument("x", default_value="0.0", description="Spawn X (m)."),
        DeclareLaunchArgument("y", default_value="0.0", description="Spawn Y (m)."),
        DeclareLaunchArgument("z", default_value="0.2", description="Spawn Z (m)."),
        DeclareLaunchArgument("yaw", default_value="0.0", description="Spawn yaw (rad)."),
]


def _launch_description(ctx):
    description_pkg = LaunchConfiguration("description_pkg")
    xacro_file = LaunchConfiguration("xacro_file")
    world_file = LaunchConfiguration("world_file")

    # Entity Start Position
    x = LaunchConfiguration("x")
    y = LaunchConfiguration("y")
    z = LaunchConfiguration("z")
    yaw = LaunchConfiguration("yaw")

    # select + published selected urdf to /robot_description
    xacro_path = PathJoinSubstitution([
        FindPackageShare(description_pkg),
        xacro_file,
    ])

    world_path = PathJoinSubstitution([
        FindPackageShare(description_pkg),
        world_file,
    ])
    robot_description = ParameterValue(
        Command(["xacro", " ",xacro_path]),
        value_type=str,
    )

    gazebo_params_file = PathJoinSubstitution([
        FindPackageShare("chassis_bringup"),
        "config",
        "gz_params.yaml"
    ])

    # launch gazebo sim
    gz_sim_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare("ros_gz_sim"),
                "launch",
                "gz_sim.launch.py"
            ])
        ),
        # gz launch always declares gz_args as a string and PathJoinSubstiution is lazily 
        # evaluated at runtime so  we must eval here to pass as a gz_arg
        launch_arguments={
            #"gz_args": f"-r -v 4 {world_path.perform(ctx)}",
            "gz_args": f"-r -v 4 empty.sdf",
            "extra_gz_args": f"--ros-args --params-file {gazebo_params_file}",
            "on_exit_shutdown": "true",
        }.items(),
    )

    # This appends your description package share directory to the resource path.
    set_resource_path = SetEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH",
        value=PathJoinSubstitution([FindPackageShare(description_pkg)]),
    )

    # publish robot_description
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="screen",
        parameters=[{"robot_description": robot_description, "use_sim_time": True}],
    )

    # Keep all Gazebo/ROS topic mappings in config files so node
    # can be maintained without changing this launch file.
    bridge_config = PathJoinSubstitution([
        FindPackageShare("chassis_bringup"),
        "config",
        "config.yaml",
    ])

    zed_bridge_config = PathJoinSubstitution([
        FindPackageShare("chassis_bringup"),
        "config",
        "zed_config.yaml",
    ])

    gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        parameters=[{"config_file": bridge_config}],
        output="screen",
    )

    zed_gz_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        parameters=[{"config_file": zed_bridge_config}],
        output="screen",
    )

    #Spawn the robot from /robot_description into Gazebo ---
    spawn_entity = Node(
        package="ros_gz_sim",
        executable="create",
        output="screen",
        arguments=[
            "-name", "BILLEE_BOT",
            "-topic", "robot_description",
            "-x", x, "-y", y, "-z", z,
            "-Y", yaw,
        ],
    )

    diff_drive_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["diff_drive_controller", "joint_state_broadcaster"]
    )

    return set_env + [
            set_resource_path,
            gz_sim_launch,
            gz_bridge,
            zed_gz_bridge,
            robot_state_publisher,
            spawn_entity,
            diff_drive_controller_spawner,
        ]

def generate_launch_description():
    #Must use an Opaque function because there are some lazily eval expressions that must be executed
    #beforehand because the args params for launch actions depend on them (world.sdf)
    #IMPORTANT: we must declare args before passing the OpaqueFunction or else it will
    #try to reference LaunchConfiguration objs that do not yet exist (havent been delcared)
    return LaunchDescription(declare_args + [
        OpaqueFunction(function=_launch_description)
    ])
