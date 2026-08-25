from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch_ros.parameter_descriptions import ParameterValue
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch.actions import OpaqueFunction
from launch_ros.substitutions import FindPackageShare

import os
from ament_index_python.packages import get_package_share_directory

desc_share = get_package_share_directory("robot_description")  
share_root = os.path.dirname(desc_share)                         

# environment variables required for GZ to render models properly
set_env = [
    SetEnvironmentVariable("IGN_GAZEBO_MODEL_PATH", share_root),
    SetEnvironmentVariable("IGN_GAZEBO_RESOURCE_PATH", share_root),
    SetEnvironmentVariable("GZ_SIM_MODEL_PATH", share_root),
    SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH", share_root),
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

    lander_path = PathJoinSubstitution([
        FindPackageShare(description_pkg),
        'urdf/lander.urdf.xacro'
    ])

    world_path = PathJoinSubstitution([
        FindPackageShare(description_pkg),
        world_file,
    ])
    robot_description = ParameterValue(
        Command(["xacro", " ",xacro_path]),
        value_type=str,
    )
    lander_description = ParameterValue(
        Command(["xacro", " ",lander_path]),
        value_type=str,
    )

    world_name = world_file.perform(ctx).split('.')[0]

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

    # Bridge /clock so ROS nodes use simulation time (critical for controllers / Nav2)
    '''
    clock_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
        output="screen",
    )
    '''

    cmd_vel_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/model/BILLEE_BOT/cmd_vel@geometry_msgs/msg/Twist]ignition.msgs.Twist",
        ],
        remappings=[('/model/BILLEE_BOT/cmd_vel', '/cmd_vel')],
        output="screen",
    )

    odom_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/model/BILLEE_BOT/odometry@nav_msgs/msg/Odometry[ignition.msgs.Odometry",
        ],
        remappings=[
            ("/model/BILLEE_BOT/odometry", "/odom"),
        ],
        output="screen",
    )
    tf_bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/model/BILLEE_BOT/tf@tf2_msgs/msg/TFMessage[ignition.msgs.Pose_V",
        ],
        remappings=[
            ("/model/BILLEE_BOT/tf", "/tf"),
        ],
        output="screen",
    )

    joint_state_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            f'/world/{world_name}/model/BILLEE_BOT/joint_state@sensor_msgs/msg/JointState[gz.msgs.Model'
        ],
        remappings=[
            (f'/world/{world_name}/model/BILLEE_BOT/joint_state', '/joint_states'),
        ],
        output='screen'
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


    #print(lander_description.evaluate(ctx))
    lander_description = lander_description.evaluate(ctx)


    spawn_launcher = Node(
        package="ros_gz_sim",
        executable="create",
        output="screen",
        arguments=[
            "-name", "Lander",
            "-string", lander_description,
        ],
    )


    return set_env + [
            set_resource_path,
            gz_sim_launch,
            odom_bridge,
            tf_bridge,
            joint_state_bridge,
            cmd_vel_bridge,
            robot_state_publisher,
            spawn_entity,
            #spawn_launcher
        ]

def generate_launch_description():

    #Must use an Opaque function because there are some lazily eval expressions that must be executed
    #beforehand because the args params for launch actions depend on them (world.sdf)
    #IMPORTANT: we must declare args before passing the OpaqueFunction or else it will
    #try to reference LaunchConfiguration objs that do not yet exist (havent been delcared)
    return LaunchDescription(declare_args + [
        OpaqueFunction(function=_launch_description)
    ])


