#!/bin/bash
set -e

export ROS_DOMAIN_ID=0

# Welcome information
echo "ZED ROS2 Docker Image"
echo "---------------------"
echo 'ROS distro: ' $ROS_DISTRO
echo 'DDS middleware: ' $RMW_IMPLEMENTATION
echo 'ROS 2 Workspaces:' $COLCON_PREFIX_PATH
echo 'ROS 2 Domain ID:' $ROS_DOMAIN_ID
echo ' * Note: Host and Docker image Domain ID must match to allow communication'
echo 'Local IPs:' $(hostname -I)
echo "---"  
echo 'Available ZED packages:'
pixi run ros2 pkg list | grep zed
echo "---------------------"
echo 'To start a ZED camera node:'
echo '  ros2 launch zed_wrapper zed_camera.launch.py camera_model:=<zed|zedm|zed2|zed2i|zedx|zedxm|zedxonegs|zedxone4k|zedxonehdr|virtual>'
echo "---------------------"
exec "$@"