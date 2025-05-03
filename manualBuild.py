import os
import subprocess
import time

# List of stages in the order they should be built
stages = [
    "track-f-build",
    "base",
    "track-b-pre-build",
    "track-b-build",
    "track-f-test",
    "track-f-final",
    "pre-build",
    "build",
    "track-d-pre-build",
    "track-c-pre-build",
    "track-c-build",
    "track-d-build",
    "track-d-test",
    "track-h-pre-build",
    "track-d-final",
    "track-b-test",
    "track-e-build",
    "track-e-final",
    "track-b-final",
    "track-a-build",
    "track-a-test",
    "test",
    "track-h-build",
    "track-h-final",
    "final",
    "track-e-test",
    "track-a-final",
    "track-c-test",
    "track-c-final"
]

# Mapping of stage names to their Dockerfile directories
stage_to_directory = {
    "track-f-build": "playground/top/second_B/second_B_third_F",
    "base": "playground/top/second_A/main",
    "track-b-pre-build": "playground/top/second_A/second_A_third_B",
    "track-b-build": "playground/top/second_A/second_A_third_B",
    "track-f-test": "playground/top/second_B/second_B_third_F",
    "track-f-final": "playground/top/second_B/second_B_third_F",
    "pre-build": "playground/top/second_A/main",
    "build": "playground/top/second_A/main",
    "track-d-pre-build": "playground/top/second_B/second_B_third_D",
    "track-c-pre-build": "playground/top/second_B/second_B_third_C",
    "track-c-build": "playground/top/second_B/second_B_third_C",
    "track-d-build": "playground/top/second_B/second_B_third_D",
    "track-d-test": "playground/top/second_B/second_B_third_D",
    "track-h-pre-build": "playground/top/second_B/second_B_third_H",
    "track-d-final": "playground/top/second_B/second_B_third_D",
    "track-b-test": "playground/top/second_A/second_A_third_B",
    "track-e-build": "playground/top/second_B/second_B_third_E",
    "track-e-final": "playground/top/second_B/second_B_third_E",
    "track-b-final": "playground/top/second_A/second_A_third_B",
    "track-a-build": "playground/top/second_A/second_A_third_A",
    "track-a-test": "playground/top/second_A/second_A_third_A",
    "test": "playground/top/second_A/main",
    "track-h-build": "playground/top/second_B/second_B_third_H",
    "track-h-final": "playground/top/second_B/second_B_third_H",
    "final": "playground/top/second_A/main",
    "track-e-test": "playground/top/second_B/second_B_third_E",
    "track-a-final": "playground/top/second_A/second_A_third_A",
    "track-c-test": "playground/top/second_B/second_B_third_C",
    "track-c-final": "playground/top/second_B/second_B_third_C"
}

# Base directory for the project
base_directory = "/home/user/dockerBuilds/prebakeGooder"

# Start timing
start_time = time.time()

# Iterate through the stages and build each Dockerfile
for stage in stages:
    directory = stage_to_directory.get(stage)
    if not directory:
        print(f"Directory for stage '{stage}' not found. Skipping...")
        continue

    full_path = os.path.join(base_directory, directory)
    dockerfile_path = os.path.join(full_path, "Dockerfile")

    if not os.path.exists(dockerfile_path):
        print(f"Dockerfile not found for stage '{stage}' in directory '{full_path}'. Skipping...")
        continue

    print(f"Building Dockerfile for stage '{stage}' in directory '{full_path}'...")
    try:
        subprocess.run(
            ["docker", "build", "-t", stage, full_path],
            check=True
        )
        print(f"Successfully built stage '{stage}'.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to build stage '{stage}'. Error: {e}")

# End timing
end_time = time.time()

# Calculate and display runtime
runtime = end_time - start_time
print(f"\nTotal runtime: {runtime:.2f} seconds")