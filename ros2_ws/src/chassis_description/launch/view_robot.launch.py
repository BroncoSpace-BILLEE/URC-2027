from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    pkg_share = get_package_share_directory("chassis_description")

    # If your file is a plain URDF:
    #urdf_path = os.path.join(pkg_share, "urdf", "my_robot.urdf")

    # If it’s xacro, change to:
    urdf_path = os.path.join(pkg_share, "urdf", "chassis_model.xacro")

    import xacro
    robot_description = xacro.process_file(urdf_path).toxml()

    return LaunchDescription([
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            parameters=[{"robot_description": robot_description}],
            output="screen",
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            output="screen",
        ),
        Node(
        package="joint_state_publisher_gui",
        executable="joint_state_publisher_gui",
        output="screen",
        ),

    ])
