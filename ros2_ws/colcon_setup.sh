#!/usr/bin/env bash

if [ -f "${CONDA_PREFIX}/share/colcon_argcomplete/hook/colcon-argcomplete.bash" ]; then
  source "${CONDA_PREFIX}/share/colcon_argcomplete/hook/colcon-argcomplete.bash"
fi

if [ -f "${CONDA_PREFIX}/share/colcon_cd/function/colcon_cd.sh" ]; then
  source "${CONDA_PREFIX}/share/colcon_cd/function/colcon_cd.sh"
fi
