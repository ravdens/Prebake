import os
import re
from pathlib import Path
import time
import colorama
from colorama import Fore, Style
import logging, sys
import argparse
import pdb
import random
import json
import multiprocessing
import copy

logging.basicConfig(
    stream=sys.stdout,
    level=logging.WARNING,
    format="%(message)s"  # print just the message.
)

# region Data Objects

class DockerStage:
    def __init__(self, file_path, base_image, stage_name):
        self.file_path = Path(file_path)
        self.stage_name = stage_name
        
        self.explored = False
        self.grouped = False

        self.base_image = base_image
        self.registry = None
        self.version_tag = None

        if "/" in base_image:
            last_slash_index = base_image.rfind("/")
            # Save everything upto and including the last / character as the registry
            self.registry = base_image[:last_slash_index + 1]

            # Save everything after the last / character as the base image name
            self.base_image = base_image[last_slash_index + 1:]

        if ":" in self.base_image:
            # Save everything after the last : character as the tag
            self.version_tag = self.base_image.split(":")[1]
            # Save everything before the last : character as the base image name
            self.base_image = self.base_image.split(":")[0]

        # Usage dependencies will init empty but be filled later
        # Set data structure to help dedup
        self.usage_dependencies = set()
        self.usage_dependencies_list = []

    def add_dependency(self, dependency):
        """
        Params:
            - str dependency: The name of the stage that this stage depends on.
        """
        if type(dependency) != str:
            raise ValueError("Dependency must be a string")
        
        self.usage_dependencies.add(dependency)

    def get_all_dependencies(self):
        """
        Returns:
            - set: A set of all dependencies for this stage, including the base image.
        """
        all_dependencies = self.usage_dependencies.copy()
        # Include the base image as a dependency
        all_dependencies.add(self.base_image)
        return all_dependencies
    
    def init_optimize_dependencies_list(self):
        """
        Initialize the usage dependencies list with the base image and all dependencies.
        """
        self.usage_dependencies_list = list(self.get_all_dependencies())

    
    def remove_version(self, image_name_with_version):
        """
        Remove the version from a specified dependency name.
        
        Params:
            - str image_name: The name of the image to remove the version from.
        """
        if ":" in image_name_with_version:
            updated_dependencies = set()
            for dep in self.usage_dependencies:
                if dep == image_name_with_version:
                    updated_dependencies.add(dep.split(":")[0])
                else:
                    updated_dependencies.add(dep)
            self.usage_dependencies = updated_dependencies

            if image_name_with_version == self.base_image:
                self.base_image = self.base_image.split(":")[0]

    def get_registry_value(self):
        """
        Getter for the registry value. Returns empty string if None.
        Returns:
            - str: The registry value for this stage.
        """
        return self.registry if self.registry is not None else ""
    
    def show(self):
        """
        Prints the stage name and its dependencies.
        """

        # Another lazy trick. Get display to be aligned
        padding = 40 - len(self.stage_name)
        str_padding = " " * padding
        return f"Stage: {self.stage_name}{str_padding}Dependencies: {self.get_all_dependencies()}"
    
    def __eq__(self, other):
        if not isinstance(other, DockerStage):
            return NotImplemented
        return self.file_path == other.file_path and self.stage_name == other.stage_name and self.base_image == other.base_image

    def __repr__(self):
        return f"File: {self.file_path} ---- FROM: {self.base_image} AS {self.stage_name}"






# endregion

# region Parsing Dockerfiles
def find_dockerfiles(root_dir):
    """
    Recursively find all Dockerfiles in the given directory and its subdirectories.

    Params: 
        - root_dir    str: The root directory to search for Dockerfiles.
    Returns:
        - List[str]:  A list of paths to Dockerfiles found in the directory and its subdirectories.
    """
    return [os.path.join(dp, f) for dp, dn, filenames in os.walk(root_dir) for f in filenames if f == 'Dockerfile']

def parse_dockerfiles(root_dir):
    """
    Parse Dockerfiles in the given directory and create DockerStage objects for each stage found.

    Params:
        - str       root_dir: The root directory to search for Dockerfiles.
    Returns: 
        - stages    List[DockerStage]: A list of DockerStage objects representing the stages found in the Dockerfiles.
    """
    stages = []

    from_pattern = re.compile(r'^FROM\s+([^\s]+)\s+AS\s+(\S+)', re.IGNORECASE)
    copy_from_pattern = re.compile(r'COPY\s+--from=([^\s]+)', re.IGNORECASE)
    mount_from_pattern = re.compile(r'--mount=.*?from=([^\s,\\]+)', re.IGNORECASE)

    for file in find_dockerfiles(root_dir):
        with open(file, 'r') as f:
            lines = f.readlines()

        processing_stage = None
        for line in lines:
            stage_match = from_pattern.match(line.strip())
            
            if stage_match:

                # If we have a processing stage, add it to the list before starting a new one
                if processing_stage is not None:
                    stages.append(processing_stage)

                base, alias = stage_match.groups()

                processing_stage = DockerStage(file, base, alias)

            for copy_match in copy_from_pattern.finditer(line):
                processing_stage.add_dependency(copy_match.group(1))

            for mount_match in mount_from_pattern.finditer(line):
                processing_stage.add_dependency(mount_match.group(1))

        # Lazy way to make sure we got the last stage
        if processing_stage is not None:
            if processing_stage not in stages:
                stages.append(processing_stage)
            processing_stage = None

    return stages

def find_crossover_stages(stages):
    """
    Find stages that are used in multiple Dockerfiles. Cross-over stages are those that are referenced in multiple Dockerfiles.
    These need to be tagged when creating the docker bake file.
    Params:
        - stages: list[DockerStage] list of stages to check for crossover
    Returns:
        - list[str]: A list of stage names that are used in multiple Dockerfiles.
    """

    crossover_stages = set()

    # Get all unique Dockerfile paths
    dockerfile_paths = set()
    for stage in stages:
        dockerfile_paths.add(stage.file_path)
    
    # For each Dockerfile, find stages and check for crossovers
    for file_path in dockerfile_paths:
        # Parse the Dockerfile to find all FROM...AS statements
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find all FROM...AS statements
        from_pattern = re.compile(r'^FROM\s+([^\s]+)\s+AS\s+(\S+)', re.IGNORECASE | re.MULTILINE)
        copy_from_pattern = re.compile(r'COPY\s+--from=([^\s]+)', re.IGNORECASE)
        mount_from_pattern = re.compile(r'--mount=.*?from=([^\s,\\]+)', re.IGNORECASE)

        matches = from_pattern.findall(content)
        for base_image, stage_name in matches:
            # Deal with versioning that crossover images will have in their non-native Dockerfile
            if ":" in base_image:
                base_image = base_image.split(":")[0]
            for stage in stages:
                if stage.stage_name == base_image and stage.file_path != file_path:
                    # Check if this stage exists in a different Dockerfile
                    if stage.file_path != file_path:
                        crossover_stages.add(stage.stage_name)

        copy_matches = copy_from_pattern.findall(content)
        for base_image in copy_matches:
            for stage in stages:
                if stage.stage_name == base_image and stage.file_path != file_path:
                    # Check if this stage exists in a different Dockerfile
                    if stage.file_path != file_path:
                        crossover_stages.add(stage.stage_name)

        mount_matches = mount_from_pattern.findall(content)
        for base_image in mount_matches:
            for stage in stages:
                if stage.stage_name == base_image and stage.file_path != file_path:
                    # Check if this stage exists in a different Dockerfile
                    if stage.file_path != file_path:
                        crossover_stages.add(stage.stage_name)

    return crossover_stages

# endregion

# region Logic Sorting

def find_stage_by_name(stages, name):
    """
    Get a known DockerStage object by its name in the list of stages.
    
    Params:
        - stages   list[DockerStage]: list of stages to search
        - name     str: name of the stage to find
    Returns:
        - DockerStage: The found stage or None if not found.
    """
    for stage in stages:
        if stage.stage_name == name:
            return stage
    return None

# TODO: Clean this global var up
recursion_depth = 0

def deep_dependency_search(stages, unresolved_set, crossover_stages):
    """
    Perform a deep search for dependencies in the list of stages. Uses recursion to find all dependencies for each stage.
    Does not return value. Modifies the stage object directly.

    Params:
        - stages: list[DockerStage] list of stages to search for dependencies
    Returns:
        - None
    """
    # Preserve the original stages for look ups
    original_stages = stages.copy()

    for stage in stages:
        global recursion_depth
        if args.verbose:
            cli_warning(f"previous depth: {recursion_depth}")
            cli_warning(f"Checking stage: {stage.stage_name}")
        recursion_depth = 0
        # If the stage has already been explored, skip it
        if stage.explored:
            continue
        else:
            orig_stage = find_stage_by_name(original_stages, stage.stage_name)
            deep_recursion(original_stages, orig_stage, stage, unresolved_set, crossover_stages)
            stage.explored = True
        

def deep_recursion(original_stages, examine_stage, record_to_stage, unresolved_set, crossover_stages):
    """
    Recursively find all dependencies for a given stage and add them to the record_to_stage.
    Does not return value. Modifies the stage object directly.

    Params:
        - original_stages   list[DockerStage]: The original list of stages to search for dependencies.
        - examine_stage     DockerStage: The stage to examine for dependencies.
        - record_to_stage   DockerStage: The stage to which the dependencies will be added.
        - unresolved_set    set(): Modified to set(string) A set to keep track of unresolved dependencies.
    Returns:
        - None
    """
    examine = examine_stage.get_all_dependencies()

    if examine is not None:
        # If the stage has already been explored, we don't need to learn the dependencies again
        if record_to_stage.explored:
            for dep in examine:
                record_to_stage.add_dependency(dep)
        else:
            global recursion_depth
            recursion_depth += 1
            for dependency in examine_stage.get_all_dependencies():

                # Check if the dependency is local or not
                if clarify_local_image(dependency, original_stages):
                    # If it's a local image, remove the version and add it to the dependencies
                    record_to_stage.remove_version(dependency)
                    # Since it's local, strip the version name moving forward
                    dependency = dependency.split(":")[0]

                # Check if the dependency is a valid stage name
                # Sloppy. Clean up?
                original_stage_names = []
                for orig_stage in original_stages:
                    original_stage_names.append(orig_stage.stage_name)

                if dependency not in original_stage_names:
                    error_message = (
                        Fore.RED +
                        "\n************************************************************\n"
                        f"ERROR: Dependency '{dependency}' not found for stage '{examine_stage.stage_name}'.\n"
                        "************************************************************\n"
                        + Style.RESET_ALL
                    )
                    logging.info(error_message)
                    unresolved_set.add(dependency)

                else:
                    the_dependency = find_stage_by_name(original_stages, dependency)
                    dependents_dependencies = the_dependency.get_all_dependencies()

                    # Add to the dependencies of stages. Preserve original stages object
                    for dep in dependents_dependencies:
                        dep_stage = find_stage_by_name(original_stages, dep)
                        record_to_stage.add_dependency(dep)

                        # recursion point
                        if dep_stage is not None:
                            deep_recursion(original_stages, dep_stage, record_to_stage, unresolved_set, crossover_stages)
                        else:
                            error_message = (
                                Fore.RED +
                                "\n************************************************************\n"
                                f"Unable to find go past dependency: {dep} for stage: {examine_stage.stage_name}.\n"
                                "************************************************************\n"
                                + Style.RESET_ALL
                            )
                            logging.info(error_message)
                            unresolved_set.add(dep)
    else:
        logging.info(Fore.RED + f"Stage {examine_stage.stage_name} has no dependencies." + Style.RESET_ALL)
        
def check_no_duplicates(stages):
    """
    Check for duplicate stage names in the list of stages.

    Params:
        - stages: list[DockerStage] list of stages to check for duplicates
    """
    duplicates = False
    seen_names = []
    for stage in stages:
        if stage.stage_name in seen_names:
            cli_error(f"Duplicate stage name found: {stage.stage_name} in {stage.file_path}")
            duplicates = True
        else:
            seen_names.append(stage.stage_name)

    if duplicates:
        cli_error("Exiting due to duplicate stage names.")
        exit(1)

def clarify_local_image(seeking_clarification, stages):
    """
    Some base images are actually local images that should be pushed to a registry during the build process. This is a complication unique to multi multistage
    docker builds. Attempt to clarify.
    Params:
        - seeking_clarification: str: The name of the image to check for local images.
        - stages: list[DockerStage] list of stages to check for unresolved dependencies
    Returns:
        - Bool: True if the image is a local image, False otherwise.
    """
    if ":" in seeking_clarification:
        for stage in stages:
            if stage.stage_name == seeking_clarification.split(":")[0]:
                return True

    return False

class OneTimeBoolean:
    """
    Sticky boolean. Can never be flipped back to True once the action to mark it as False is called.
    """
    @property
    def status(self):
        return self.mark

    def __init__(self):
        self.mark = False
        self.finished = False

    def mark_true(self):
        """
        Set the marker to True.
        """
        if not self.finished:
            self.mark = True
    
    def mark_false(self):
        """
        Set the marker to False.
        """
        self.finished = True
        self.mark = False


def group_stages_by_build_order(stages, unresolved_set):
    """
    Group Docker stages
    Params:
        - stages: list[DockerStage] list of stages to group by build order
        - unresolved_set: set() set of unresolved dependencies
    Returns:
        - list[list[DockerStage]]: A list of groups of stages that can be built in parallel.
    """


    def order_stages_by_dependency_count(stages, descending=False):
        """
        Order Docker stages based on the number of dependencies they have.
        
        Params:
            - stages: list[DockerStage] - list of stages to sort
            - descending: bool - if True, sort in descending order (most dependencies first)
        Returns:
            - list[DockerStage]: Stages ordered by dependency count
        """
        return sorted(stages, key=lambda stage: len(stage.get_all_dependencies()), reverse=descending)
    
    
    def kahns_algo(stages, unresolved_dependencies=None):
        unresolved_dependencies = unresolved_dependencies or set()
        name_to_stage = {stage.stage_name: stage for stage in stages}
        visited = set()
        temp_marks = set()
        sorted_list = []

        def visit(stage):
            if stage.stage_name in temp_marks:
                raise ValueError(f"Circular dependency detected: {stage.stage_name}")
            if stage.stage_name not in visited:
                temp_marks.add(stage.stage_name)
                for dep_name in stage.get_all_dependencies():
                    if dep_name in unresolved_dependencies:
                        continue  # It's a base image, not a stage we control
                    if dep_name not in name_to_stage:
                        raise ValueError(f"Dependency '{dep_name}' not found for stage '{stage.stage_name}'")
                    visit(name_to_stage[dep_name])
                temp_marks.remove(stage.stage_name)
                visited.add(stage.stage_name)
                sorted_list.append(stage)

        for stage in stages:
            visit(stage)

        return sorted_list
    
    # TODO: benchmark sorted and unsorted. Gambling that this is dumb and marginally faster
    stages = order_stages_by_dependency_count(stages)

    if args.verbose:
        cli_middle("Pre kahns - stage order")
        for item in stages:
            cli_info(f" {item.show()}")
        cli_div()

    stages = kahns_algo(stages, unresolved_set)

    if args.verbose:
        cli_middle("Pre Grouping - stage order")
        for item in stages:
            cli_info(f" {item.show()}")
        cli_div()

    def group_stages_by_dependency_barrier(ordered_stages, unresolved_set):
        seen_names = unresolved_set.copy()
        satisfied_names = unresolved_set.copy()
        all_groups = []
        current_group = []
        for idx, stage in enumerate(ordered_stages):
            # Add the stage to the seen names set
            seen_names.add(stage.stage_name)
            to_be_satisfied_names = set()
            add_to_group = OneTimeBoolean()

            for dep_name in stage.get_all_dependencies():

                if dep_name not in seen_names and dep_name not in satisfied_names:
                    # who cares, probably an unresolved dependency
                    if dep_name not in unresolved_set:
                        cli_warning(f"{dep_name} not an unresolved dependency. Unexpected to have not seen it before.")

                elif dep_name not in seen_names and dep_name in satisfied_names:
                    # Mark this to add. We might bail if we find a dependency that is not satisfied
                    add_to_group.mark_true()

                # Seen and not satisfied, create new group
                elif dep_name in seen_names and dep_name not in satisfied_names:
                    to_be_satisfied_names.add(dep_name)
                    add_to_group.mark_false()

                    
                elif dep_name in seen_names and dep_name in satisfied_names:
                    # All is good. Add to current group if not in there and continue
                    add_to_group.mark_true()

            # After reading all of a stages dependencies, check if we can add to the group
            if add_to_group.status:
                # Add to the current group if the last dependency is not in the seen names
                if stage not in current_group:
                    to_be_satisfied_names.add(stage.stage_name)
                    current_group.append(stage)
            else:
                all_groups.append(current_group)
                # If we're flushing the group and starting a new one, then go ahead and mark all of the stages that are in the group to be
                #    flushed as satisfied. They're all blessed now and already built.
                for dep_stage in current_group:
                    to_be_satisfied_names.add(dep_stage.stage_name)
                current_group = []
                current_group.append(stage)
                for dep_name in to_be_satisfied_names:
                    satisfied_names.add(dep_name)

        # Check if it's the last item
        if idx == len(ordered_stages) - 1:  
            all_groups.append(current_group)

        return all_groups
    
    group_list = group_stages_by_dependency_barrier(stages, unresolved_set)

    return group_list

# endregion

# region File Logic
def validate_directory(directory):
    """
    Validate if the given directory exists and is a directory.

    Params:
        - directory: str: The directory to validate.
    Returns:
        - bool: True if the directory exists and is a directory, False otherwise.
    """
    if os.path.isdir(directory):
        return True
    else:
        print(Fore.RED + f"# Error: {directory} is not a valid directory." + Style.RESET_ALL)
        exit(1)

def create_docker_bake_hcl(sorted_groups, crossover_images, tag, output_file="docker_bake.hcl"):
    """
    Create a Docker Bake HCL file based on the sorted groups of DockerStage objects.
    
    Params:
        - sorted_groups: list[list[DockerStage]] - groups of stages that can be built in parallel.
        - output_file: str - name/path of the output HCL file.
    Returns:
        - None : writes file to disk when called.
    """

    
    # Generate the bake hcl output
    # 0 = no output. 1 = registry, 2 = local, 3 = registry, local.
    output = None
    if args.output != 0:
        if args.output == 1:
            output = '"type=registry"'
        elif args.output == 2:
            output = '"type=docker"'
        elif args.output == 3:
            output = '"type=registry" "type=docker"'
        output = f"output = [{output}]"
    

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write('// Docker Bake HCL file generated automatically with Prebake\n\n')

            # Collect and write all top-level target blocks
            all_written = set()
            for group in sorted_groups:
                for stage in group:
                    if stage.stage_name in all_written:
                        continue
                    all_written.add(stage.stage_name)
                    f.write(f'target "{stage.stage_name}" {{\n')
                    f.write(f'  dockerfile = "{stage.file_path}"\n')
                    f.write(f'  target     = "{stage.get_registry_value()}{stage.stage_name}"\n')
                    f.write( '  args = {\n')
                    f.write(f'    BASE_IMAGE = "{stage.base_image}"\n')
                    f.write( '  }\n')
                    if stage.stage_name in crossover_images:
                        f.write(f'  tags = ["{stage.stage_name}:{tag}"]\n')
                        #TODO: decide if determining output by checking if tag is none or by in cross over is better
                        f.write(f'  {output}\n')
                    f.write( '  cache-to = [ ]\n')
                    f.write( '  cache-from = [ ]\n')
                    f.write("}\n\n")

            # Now write the groups
            for idx, group in enumerate(sorted_groups, start=1):
                group_name = f"group{idx}"
                target_names = [f'"{stage.stage_name}"' for stage in group]
                f.write(f'group "{group_name}" {{\n')
                f.write(f'  targets = [{", ".join(target_names)}]\n')
                f.write("}\n\n")

        cli_info(f"Successfully created {output_file}")

    except Exception as e:
        cli_error(f"Error writing to file {output_file}:")
        cli_error(str(e))

def create_docker_bake_json(sorted_groups, crossover_images, tag, output_file="docker_bake.hcl"):
    """
    Create a Docker Bake JSON file based on the sorted groups of DockerStage objects.
    
    Params:
        - sorted_groups: list[list[DockerStage]] - groups of stages that can be built in parallel.
        - crossover_images: list[str] - list of crossover images to be tagged.
        - tag: str - tag to use for the Docker Bake JSON configuration.
        - output_file: str - name/path of the output JSON file.
    Returns:
        - None : writes file to disk when called.
    """

    
    bake_json = {
        "target": {},
        "group": {}
    }

    # Generate targets
    for group in sorted_groups:
        for stage in group:
            target = {
                "dockerfile": str(stage.file_path),
                "target": f"{stage.get_registry_value()}{stage.stage_name}",
                "args": {
                    "BASE_IMAGE": stage.base_image
                },
                "cache-to": [],
                "cache-from": []
            }
            if stage.stage_name in crossover_images:
                target["tags"] = [f"{stage.stage_name}:{tag}"]
                # Add output if applicable
                if args.output != 0:
                    if args.output == 1:
                        target["output"] = ["type=registry"]
                    elif args.output == 2:
                        target["output"] = ["type=docker"]
                    elif args.output == 3:
                        target["output"] = ["type=registry", "type=docker"]
            bake_json["target"][stage.stage_name] = target

    # Generate groups
    for idx, group in enumerate(sorted_groups, start=1):
        group_name = f"group{idx}"
        target_names = [stage.stage_name for stage in group]
        bake_json["group"][group_name] = {
            "targets": target_names
        }

    # Write to file
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(bake_json, f, indent=4)
        cli_info(f"Successfully created {output_file}")
    except Exception as e:
        cli_error(f"Error writing to file {output_file}:")
        cli_error(str(e))

# endregion

# region Optimize Logic

def _run_single_optimization_attempt(args_tuple):
    """
    Worker function for parallel optimization. Must be at module level for pickling.
    
    Params:
        - args_tuple: tuple containing (stages_data, unresolved_set, crossover_stages, attempt_id)
    Returns:
        - list[list[dict]]: A list of groups with stage data for this attempt.
    """
    stages_data, unresolved_set, crossover_stages = args_tuple
    
    # Reconstruct DockerStage objects from serialized data
    reconstructed_stages = []
    for stage_data in stages_data:
        stage = DockerStage.__new__(DockerStage)
        stage.file_path = Path(stage_data['file_path'])
        stage.stage_name = stage_data['stage_name']
        stage.base_image = stage_data['base_image']
        stage.registry = stage_data['registry']
        stage.version_tag = stage_data['version_tag']
        stage.usage_dependencies = set(stage_data['usage_dependencies'])
        stage.usage_dependencies_list = list(stage_data['usage_dependencies_list'])
        stage.explored = False
        stage.grouped = False
        reconstructed_stages.append(stage)
    
    # Randomize dependencies for this attempt
    for stage in reconstructed_stages:
        random.shuffle(stage.usage_dependencies_list)
    
    # Run dependency search
    for stage in reconstructed_stages:
        if stage.explored:
            continue
        else:
            orig_stage = find_stage_by_name(reconstructed_stages, stage.stage_name)
            deep_recursion(reconstructed_stages, orig_stage, stage, unresolved_set, crossover_stages)
            stage.explored = True
    
    deep_dependency_search(reconstructed_stages, unresolved_set, crossover_stages)
    attempt_sorted_groups = group_stages_by_build_order(reconstructed_stages, unresolved_set)
    
    return attempt_sorted_groups


def _serialize_stages(stages):
    """
    Serialize DockerStage objects to dictionaries for multiprocessing.
    """
    return [{
        'file_path': str(stage.file_path),
        'stage_name': stage.stage_name,
        'base_image': stage.base_image,
        'registry': stage.registry,
        'version_tag': stage.version_tag,
        'usage_dependencies': list(stage.usage_dependencies),
        'usage_dependencies_list': list(stage.usage_dependencies_list)
    } for stage in stages]


def optimize(stages, unresolved_set, crossover_stages, sorted_groups):
    """
    Optimize the Dockerfile stages by performing a deep dependency search and grouping them by build order.
    Minimal mutation. Only overrides the explored and grouped flags on the stages.
    Params:
        - stages: list[DockerStage] list of stages to optimize
        - unresolved_set: set() set of unresolved dependencies
        - crossover_stages: set() set of crossover stages
        - sorted_groups: list[list[DockerStage]] list of groups of stages that can be built in parallel.
    Returns:
        -sorted_groups: list[list[DockerStage]]: A list of groups of stages that can be built in parallel.
    """

    # Ensure optimization is enabled
    if args.optimize == 0:
        return
    
    # Disable verbose logging for the optimization process
    re_enable_verbose = False
    if args.verbose:
        re_enable_verbose = True
        args.verbose = False 
    
    str_num_attempts = str(args.optimize)
    
    # Determine number of cores to use
    available_cores = os.cpu_count() or 1
    max_cores = max(1, available_cores - 1)  # Enforce n-1 cores
    requested_cores = args.cores if args.cores > 0 else max_cores
    cores_to_use = min(requested_cores, max_cores)
    
    cli_info(f"Available cores: {available_cores}, Using: {cores_to_use} (max allowed: {max_cores})")
    
    # Prepare the original stages to be optimized
    for stage in stages:
        stage.init_optimize_dependencies_list()
    
    # Serialize stages for multiprocessing
    serialized_stages = _serialize_stages(stages)
    clone_unresolved_set = unresolved_set.copy()
    clone_crossover_stages = crossover_stages.copy()
    
    # Create argument tuples for each optimization attempt
    work_items = [
        (serialized_stages, clone_unresolved_set, clone_crossover_stages)
        for _ in range(args.optimize)
    ]
    
    # Run optimization attempts in parallel
    if cores_to_use > 1 and args.optimize > 1:
        with multiprocessing.Pool(processes=cores_to_use) as pool:
            grouping_attempts = pool.map(_run_single_optimization_attempt, work_items)
    else:
        # Fall back to sequential execution for single core or single attempt
        grouping_attempts = [_run_single_optimization_attempt(item) for item in work_items]

    # Determine the number of groups produced by the brute force attempts
    # Log the best and worst attempts
    best_attempt = sorted_groups
    worst_attempt = sorted_groups
    for attempt in grouping_attempts:
        if len(attempt) < len(best_attempt):
            best_attempt = attempt
        if len(attempt) > len(worst_attempt):
            worst_attempt = attempt
        
    cli_middle(f"Optimized Dockerfile...with {str_num_attempts} brute force attempts")
    cli_info(f"Fewest groupings: {len(best_attempt)}")
    cli_info(f"Fewest groupings: {len(worst_attempt)}")
    cli_info(f"Pre-optimization groupings: {len(sorted_groups)}")
    cli_div()

    # Re-enable verbose logging for the optimization process
    if re_enable_verbose:
        args.verbose = True

    return best_attempt

# endregion

# region Modify Logic

# endregion

# region CLI Display Functions

def cli_header():
    print(Fore.CYAN + "##################################################" + Style.RESET_ALL)
    print(Fore.CYAN + "##" + Style.RESET_ALL)
    print(Fore.CYAN + "##" + Style.RESET_ALL)

def cli_footer():
    print(Fore.CYAN + "##" + Style.RESET_ALL)
    print(Fore.CYAN + "##" + Style.RESET_ALL)
    print(Fore.CYAN + "##################################################" + Style.RESET_ALL)

def cli_div():
    print(Fore.CYAN + "##" + Style.RESET_ALL)
    print(Fore.CYAN + "##################################################" + Style.RESET_ALL)
    print(Fore.CYAN + "##" + Style.RESET_ALL)
    

def cli_title():
    print(Fore.CYAN + "##  PRE-BAKE" + Style.RESET_ALL)
    print(Fore.CYAN + "##  Get all your multistage docker needs done right" + Style.RESET_ALL)
    print(Fore.CYAN + "##" + Style.RESET_ALL)

def cli_sub_title(title):
    print(Fore.CYAN + "##  "+ Style.BRIGHT  + Fore.GREEN + f" {title}" + Style.RESET_ALL)

def cli_sub_title_alt(title):
    print(Fore.CYAN + "##  "+ Style.BRIGHT  + Fore.WHITE + f" {title}" + Style.RESET_ALL)

def cli_info(group):
    print(Fore.CYAN + "##   " + Style.BRIGHT + Fore.WHITE + f" {group}"+ Style.RESET_ALL)

def cli_error(error):
    print(Fore.RED + "##  " + Style.BRIGHT + Fore.RED + f"ERROR: {error}" + Style.RESET_ALL)

def cli_warning(warning):
    print(Fore.CYAN + "##  "+ Style.BRIGHT  + Fore.YELLOW + f"WARNING: {warning}" + Style.RESET_ALL)

def cli_middle(input = None):
    if input:
        print(Fore.CYAN + "##" + Style.RESET_ALL)
        print(Fore.CYAN + "##   " + Fore.WHITE + input + Style.RESET_ALL)
        print(Fore.CYAN + "##" + Style.RESET_ALL)
    else:
        print(Fore.CYAN + "##" + Style.RESET_ALL)
        print(Fore.CYAN + "##" + Style.RESET_ALL)
        print(Fore.CYAN + "##" + Style.RESET_ALL)

def cli_unresolved(unresolved_set):
    if len(unresolved_set) == 0:
        return
    
    print(Fore.CYAN + "##" + Style.RESET_ALL)
    print(Fore.CYAN + "##" + Fore.WHITE + "   Unresolved Images --" + Style.RESET_ALL)
    cli_middle()
    for unresolved in unresolved_set:
        print(Fore.CYAN + "##    " + Fore.YELLOW + unresolved + Style.RESET_ALL)
    print(Fore.CYAN + "##" + Style.RESET_ALL)
    print(Fore.CYAN + "##" + Style.RESET_ALL)

# endregion
    
# region Main
def main():
    """
    Main function.
    Params: str directory: The root directory to search for Dockerfiles.
    """

    start_time = time.time()
    cli_header()

    validate_directory(args.directory)
    root_dir = args.directory

    # Validate output bake file format
    if args.fileFormat != "hcl" and args.fileFormat != "json":
        cli_error(f"Invalid file format: {args.fileFormat}. Valid options are 'hcl' or 'json'.")
        exit(1)

    # TODO: consider a more elegant way to handle default output file names
    if args.outfile == "docker":
        if args.fileFormat == "hcl":
            args.outfile = "docker.hcl"
        else:
            args.outfile = "docker.json"

    if args.version:
        cli_sub_title("Starting Dockerfile parsing...")
        cli_middle("Prebake version: 0.1.0")
        cli_footer()
        exit(0)

    cli_sub_title("Starting Dockerfile parsing...")
    stages = parse_dockerfiles(root_dir)    

    check_no_duplicates(stages)

    cli_middle("Parsed Stages:")
    for stage in stages:
        cli_info(stage.show())
    cli_middle(f"Count: {len(stages)}")
    cli_div()

    crossover_stages = find_crossover_stages(stages)
    cli_middle("Identifying crossover stages...")
    for crossover in crossover_stages:
        cli_info(f" {crossover}")
    cli_div()

    cli_middle("Identifying custom registries...")
    for stage in stages:
        if stage.registry is not None:
            cli_info(f" {stage.registry}")
    cli_div()

    cli_middle("Identifying unique tags...")
    unique_tags = set()
    for stage in stages:
        if stage.version_tag is not None:
            unique_tags.add(stage.version_tag)
    for tag in unique_tags:
        cli_info(f" {tag}")
    cli_div()

    if args.verbose:
        cli_middle("Pre Deep dependency - stage order")
        for item in stages:
            cli_info(f" {item.show()}")
        cli_div()

    #TODO: Consider removing shuffle. Windows and Linux end up with different orderings. This creates a less efficient build order
    #  when run on Linux. In an effort to help development better target Linux, leave this shuffle in for now.
    random.shuffle(stages)

    cli_middle("Deep dependency search")
    unresolved_set = set()
    deep_dependency_search(stages, unresolved_set, crossover_stages)
    cli_middle()
    for item in stages:
        cli_info(f" {item.show()}")

    cli_div()
    cli_unresolved(unresolved_set)
    cli_div()

    sorted_groups = group_stages_by_build_order(stages, unresolved_set)

    # Optimize does not mutate. Save returned value to stages
    if args.optimize > 0:
        sorted_groups = optimize(stages, unresolved_set, crossover_stages, sorted_groups)

    cli_middle()
    cli_middle("Sorted groups by build order:")
    for group in sorted_groups:
        cli_middle(" Group:")
        for stage in group:
            cli_info(stage.show())
    cli_middle()

    cli_div()
    if args.fileFormat == "json":
        cli_middle("Creating Docker Bake JSON file...")
        create_docker_bake_json(sorted_groups, crossover_stages, args.tag, args.outfile)
    else:
        cli_middle("Creating Docker Bake HCL file...")
        create_docker_bake_hcl(sorted_groups, crossover_stages, args.tag, args.outfile)

    end_time = time.time()

    cli_footer()
    # Worth cli method for this? prob not
    print(Style.DIM + Fore.BLUE + f"\nTime taken: {(end_time - start_time) * 1000:.0f} ms{Style.RESET_ALL}")

# endregion
 
if __name__ == "__main__":
    # Required for Windows multiprocessing support
    multiprocessing.freeze_support()
    
    parser = argparse.ArgumentParser(
        description="Multi Multi-Stage Dockerfiles? Trying to move to docker baking but your dependencies are too complex?" +
    " Use this tool to help map out the dependency groups that can be built in parallel. Get a map of your dependencies and create the faster docker building you deserve."
    )

    parser.add_argument(
        "-d", "--directory", 
        type=str, 
        required=True, 
        help="Root directory to start search and parsing for Dockerfiles. Hint: make this the root directory of your project."
    )
    parser.add_argument(
        "-o", "--outfile",
        type=str,
        default=os.path.join(os.getcwd(), "docker"),
        help="Output file for Docker Bake HCL configuration. Defaults to 'docker.hcl' in the current working directory."
    )
    parser.add_argument(
        "-t", "--tag",
        type=str,
        default="prebake",
        help="Tag to use for the Docker Bake HCL configuration. Defaults to 'prebake'."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output."
    )

    parser.add_argument(
        "--optimize",
        type=int,
        default=0,
        help="Optimize the Dockerfile for faster builds. Currently brute force method. Specify the number of brute force attempts to make. Will not optimize if not set."
    )

    parser.add_argument(
        "--cores",
        type=int,
        default=0,
        help="Number of CPU cores to use for parallel optimization. Defaults to 0 (auto-detect, uses n-1 cores). Maximum is always capped at n-1 to leave one core free."
    )

    parser.add_argument(
        "--output",
        type=int,
        default=0,
        help="Output the Docker Bake HCL configuration to a file. Defaults to 0 (no output). 1 = registry, 2 = local, 3 = registry, local."
    )

    parser.add_argument(
        "--fileFormat",
        type=str,
        default="hcl",
        help="Output the Docker Bake HCL configuration to a file. Valid options are 'hcl' or 'json'. Defaults to 'hcl'."
    )

    parser.add_argument(
        "--version",
        action="store_true",
        default=False,
        help="Output version number and exit the script."
    )


    global args
    args = parser.parse_args()
    
    root_dir = args.directory
    colorama.init()
    main()
