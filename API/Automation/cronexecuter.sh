#!/bin/bash

# Initialize Conda
source ~/miniconda3/etc/profile.d/conda.sh

# Activate the Conda environment
conda activate py311

# Change directory to the target location
cd /home/ubuntu/API/V13 || exit

# Run the Python script and log all output to audit.log
python3 api.py &> audit.log
