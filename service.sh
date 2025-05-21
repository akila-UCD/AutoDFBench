#!/bin/bash

# Path to the conda executable
CONDA_PATH="/root/miniconda3/bin/conda"

# Conda environment name
CONDA_ENV="dfllm_eval"

# Path to the Python file
PYTHON_FILE="/home/ubuntu/API/DFLLM_Eval/API/Automation/api.py"

# Change to the specified directory
cd /home/ubuntu/API/DFLLM_Eval/API/Automation

# Activate the Conda environment
conda init
conda activate dfllm_eval

# Infinite loop to run the Python file every 5 minutes
while true; do
    
    # Execute the Python file
    python3 $PYTHON_FILE
    
    # Sleep for 300 seconds (5 minutes)
    sleep 300
done
