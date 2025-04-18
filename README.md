# Prebake

A tool designed to help transition from multi-stage Dockerfiles to Docker Bake configurations. Prebake helps migrate large codebases using that require multiple multistage Dockerfiles throughout a codebase to be individually built, to using Docker bake. Prebake helps to address the challenge to organizing docker images so that they can be concurrently baked without running into dependency order issues.

Tested with Python 3.10.11 and 3.10.12

## Overview

Prebake analyzes your existing multi-stage Dockerfiles and generates equivalent Docker Bake configurations. This helps modernize your containerization workflow and enables:

- Better parallelization of build steps
- Simplified management of complex build dependencies
- Improved CI/CD pipeline integration

## Limitations

It is important to note that currently multiple versions of a locally created image are not supported. Prebake assumes crossover images between multiple dockerfiles within the local project
  are all using the same version. Prebake currently does not support detecting multiple local image versions and will produce erroneous results.

Currently Prebake only produces the .hcl file used for baking. Users will have to walk the bake through each group individually at the current moment.

Currently Prebake does not support detecting circular dependencies. Unexpected and likely erroneous behavior will result from this.

Currently Prebake does not have the ability to deal with commented out FROM ... AS ... lines in dockerfiles. Crashes are unlikely but wrong results will be produced. Detection and warning for this
  is not supported yet.

Currently Prebake does not support images of the same name sourced from different repositories.

## Installation & Usage

Basic usage:

```bash
# Create a virtual environment
python -m venv venvPrebake

# Activate the virtual environment
# On Windows:
#  venv\Scripts\activate
# On macOS/Linux:
#  source venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Run prebake
python prebake -d path/to/project/root/directory
```

## Demo

The following demo will assume that you are not using a registry and will use the local Docker daemon image store.
Demo instructions are geared towards running on linux.

Note that if you set up the playground to use an example with a custom registry in one of the images, unless you have changed the dockerfile in the playground
  to point to a real custom registry, you will not actually be able to bake the file. The .hcl file will be generated correctly and Prebake will run as intended.

To try out Prebake with a sample project:

1. Install Prebake
2. Run the setup playground command from the root directory of the project:
   ```bash
   python setupPlayground.py
   ```
3. Provide the playground directory as the parameter to the -d flag when running prebake. The playground directory will be printed near the end of the setupPlayground script's output.
   ```bash
   python prebake.py -d path/to/playground
   ```
5. Visually make sure that any unresolved dependencies are correctly identified as images stored outside of your project.

6. Inspect the .hcl file produced and identify the number of groups that were created.

7. Since we are not using a network registry in this demo, and instead using the local Docker daemon image store, make sure that you are using the Default docker buildx driver.
   ```
   docker buildx ls
   ```
   Visually confirm that the default builder is selected. If not, then use the default driver.
   ```
   docker buildx use default
   ```

8. Build each group.
   ```
   docker buildx bake --load -f docker.hcl group1
   docker buildx bake --load -f docker.hcl group2
   ...
   
   ```

## Playground

Prebake comes with a playground that can be automatically setup and torn down. It's mainly intended to be used with the local Docker daemon image store, however, there exist a flag to 
  create a playground that uses an image that is supposedly pulled from a custom registry.

To set up the default playground
```
python setupPlayground.py
```

To tear down the playground
```
python setupPlayground.py --clean
```

To set up the playground with an example that uses a custom registry
```
python setupPlayground.py --customRegistry
```

## Features

- Automatic detection of build stages
- Dependency mapping between stages
- Generation of optimized Docker Bake configurations
- Support for complex build arguments and environment variables

## Requirements

- Docker
- Docker Buildx plugin
- Python 3.10.11 or 3.10.12
