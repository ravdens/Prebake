import os
import shutil
from pathlib import Path
import argparse

def ensure_directory_exists(directory_path):
    """Create directory if it doesn't exist"""
    path = Path(directory_path)
    path.mkdir(parents=True, exist_ok=True)
    
def copy_dockerfile(source_file, destination_dir):
    """Copy a dockerfile to destination directory and rename it to Dockerfile"""
    if not os.path.exists(source_file):
        print(f"Warning: Source file {source_file} does not exist")
        return
        
    # Create destination directory if it doesn't exist
    ensure_directory_exists(destination_dir)
    
    # Destination is always named Dockerfile
    destination_file = os.path.join(destination_dir, "Dockerfile")
    
    # Copy the file
    with open(source_file, "r") as src, open(destination_file, "w") as dest:
        dest.write(src.read())
    print(f"Copied {source_file} to {destination_file}")

def main():
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define playground directory
    playground = os.path.join(current_dir, "playground")
    
    # Define sample Dockerfiles directory
    sample_dockerfiles_dir = os.path.join(current_dir, "sampleDockerfiles")
    
    # Ensure playground directory structure exists
    ensure_directory_exists(playground)
    
    # Define the directory structure based on setupPlayground.py
    directories = {
        "main": os.path.join(playground, "top", "second_A", "main"),
        "trackA": os.path.join(playground, "top", "second_A", "second_A_third_A"),
        "trackB": os.path.join(playground, "top", "second_A", "second_A_third_B"),
        "trackC": os.path.join(playground, "top", "second_B", "second_B_third_C"),
        "trackD": os.path.join(playground, "top", "second_B", "second_B_third_D"),
        "trackE": os.path.join(playground, "top", "second_B", "second_B_third_E"),
        "trackF": os.path.join(playground, "top", "second_B", "second_B_third_F"),
    }

    # If customRegistry is specified, add the trackG directory
    if args.customRegistry:
        directories["trackG"] = os.path.join(playground, "top", "second_B", "second_B_third_G")
    
    # Create directories if they don't exist
    for dir_path in directories.values():
        ensure_directory_exists(dir_path)
    
    # Copy each dockerfile to its destination
    for track, dir_path in directories.items():
        # Skip trackG if customRegistry is not specified
        if track == "trackG" and not args.customRegistry:
            continue
        
        source_name = os.path.join(sample_dockerfiles_dir, f"Dockerfile_{track}")
        if os.path.exists(source_name):
            copy_dockerfile(source_name, dir_path)
        else:
            print(f"Warning: {source_name} does not exist")
    
    # Copy additional files to all directories
    app_dir = os.path.join(current_dir, "app")
    additional_files = ["requirements.txt", "app.py", "helloBase.py"]
    
    for dir_name, dir_path in directories.items():
        # Skip trackG if customRegistry is not specified
        if dir_name == "trackG" and not args.customRegistry:
            continue
        
        for file in additional_files:
            source_file = os.path.join(app_dir, file)
            if os.path.exists(source_file):
                dest_file = os.path.join(dir_path, file)
                shutil.copy2(source_file, dest_file)
                print(f"Copied {source_file} to {dest_file}")
            else:
                print(f"Warning: {file} does not exist in the app directory")

    print(f"Playground directory located at: {playground}")
    

if __name__ == "__main__":
    print("Setting up the playground and configuring Dockerfiles...")

    # Parse optional arguments
    parser = argparse.ArgumentParser(description="Setup playground directories and configure Dockerfiles.")
    parser.add_argument("--clean", action="store_true", default=False, help="Clean the playground directory before setup.")
    parser.add_argument("--customRegistry", action="store_true", default=False, help="Setup the playground with an example of using a custom repository.")

    global args
    args = parser.parse_args()

    # Clean the playground directory if the --clean flag is provided
    if args.clean:
        playground = os.path.join(os.path.dirname(os.path.abspath(__file__)), "playground")
        if os.path.exists(playground):
            shutil.rmtree(playground)
            print(f"Cleaned up the playground directory: {playground}")
        exit(0)

    
    main()
    print("Complete -- Enjoy.")