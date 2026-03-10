import os
import re
from pathlib import Path
import time
import colorama
from colorama import Fore, Style
import logging, sys
import argparse
import json

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
        self.transitive_dependencies = None

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
        Prints the stage name and its direct dependencies.
        """

        # Another lazy trick. Get display to be aligned
        padding = 40 - len(self.stage_name)
        str_padding = " " * padding
        return f"Stage: {self.stage_name}{str_padding}Dependencies: {self.get_all_dependencies()}"

    def show_verbose(self):
        """
        Prints the stage name and its transitive dependencies (if computed).
        """
        padding = 40 - len(self.stage_name)
        str_padding = " " * padding
        deps = self.transitive_dependencies if self.transitive_dependencies is not None else self.get_all_dependencies()
        return f"Stage: {self.stage_name}{str_padding}Dependencies: {deps}"
    
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
                    crossover_stages.add(stage.stage_name)

        copy_matches = copy_from_pattern.findall(content)
        for base_image in copy_matches:
            for stage in stages:
                if stage.stage_name == base_image and stage.file_path != file_path:
                    crossover_stages.add(stage.stage_name)

        mount_matches = mount_from_pattern.findall(content)
        for base_image in mount_matches:
            for stage in stages:
                if stage.stage_name == base_image and stage.file_path != file_path:
                    crossover_stages.add(stage.stage_name)

    return crossover_stages

# endregion

# region Logic Sorting

def resolve_dependencies(stages):
    """
    Normalize dependencies across all stages. Strips version tags from local image
    references and identifies unresolved (external) dependencies.

    Params:
        - stages: list[DockerStage] list of stages to resolve
    Returns:
        - set: A set of unresolved dependency names (external base images).
    """
    unresolved_set = set()
    stage_names = {stage.stage_name for stage in stages}

    for stage in stages:
        for dep in list(stage.get_all_dependencies()):
            if clarify_local_image(dep, stages):
                stage.remove_version(dep)
                dep = dep.split(":")[0]

            if dep not in stage_names:
                unresolved_set.add(dep)

    return unresolved_set

def compute_transitive_deps(stages, unresolved_set):
    """
    Compute the full transitive dependency closure for each stage and store it
    on the stage for display purposes.

    Params:
        - stages: list[DockerStage] list of stages
        - unresolved_set: set of unresolved (external) dependency names
    """
    name_to_stage = {s.stage_name: s for s in stages}
    cache = {}
    active_path = set()

    for stage in stages:
        if stage.stage_name in cache:
            stage.transitive_dependencies = cache[stage.stage_name]
            continue

        # Iterative post-order DFS
        stack = [(stage.stage_name, False)]
        while stack:
            name, deps_done = stack[-1]

            if name in cache:
                stack.pop()
                continue

            if not deps_done:
                if name in active_path:
                    raise ValueError(f"Circular dependency detected: {name}")
                active_path.add(name)
                stack[-1] = (name, True)
                for dep in name_to_stage[name].get_all_dependencies():
                    if dep in unresolved_set or dep not in name_to_stage:
                        continue
                    if dep not in cache:
                        stack.append((dep, False))
            else:
                result = set(name_to_stage[name].get_all_dependencies())
                for dep in name_to_stage[name].get_all_dependencies():
                    if dep in unresolved_set or dep not in name_to_stage:
                        continue
                    result |= cache[dep]
                cache[name] = result
                active_path.discard(name)
                stack.pop()

        stage.transitive_dependencies = cache[stage.stage_name]
        
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

def group_stages_by_build_order(stages, unresolved_set):
    """
    Group Docker stages into parallel build layers using longest-path layering.
    Each stage is assigned to the earliest layer where all its dependencies are in prior layers.
    This produces the minimum number of groups (optimal).

    Params:
        - stages: list[DockerStage] list of stages to group by build order
        - unresolved_set: set() set of unresolved dependencies
    Returns:
        - list[list[DockerStage]]: A list of groups of stages that can be built in parallel.
    """
    name_to_stage = {s.stage_name: s for s in stages}
    layer_of = {}

    for stage in stages:
        if stage.stage_name in layer_of:
            continue

        # Iterative DFS using an explicit stack to avoid recursion limits
        stack = [(stage, False)]
        active_path = set()

        while stack:
            current, deps_processed = stack[-1]

            if current.stage_name in layer_of:
                stack.pop()
                continue

            if current.stage_name in active_path and not deps_processed:
                raise ValueError(f"Circular dependency detected: {current.stage_name}")

            if not deps_processed:
                active_path.add(current.stage_name)
                stack[-1] = (current, True)
                # Push unresolved local deps onto the stack
                for dep in current.get_all_dependencies():
                    if dep in unresolved_set or dep not in name_to_stage:
                        continue
                    if dep not in layer_of:
                        stack.append((name_to_stage[dep], False))
            else:
                # All deps resolved — compute this stage's layer
                max_dep_layer = -1
                for dep in current.get_all_dependencies():
                    if dep in unresolved_set or dep not in name_to_stage:
                        continue
                    max_dep_layer = max(max_dep_layer, layer_of[dep])
                layer_of[current.stage_name] = max_dep_layer + 1
                active_path.discard(current.stage_name)
                stack.pop()

    if not layer_of:
        return []

    num_layers = max(layer_of.values()) + 1
    groups = [[] for _ in range(num_layers)]
    for stage in stages:
        groups[layer_of[stage.stage_name]].append(stage)

    # Filter out any empty groups
    groups = [g for g in groups if g]

    return groups

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
        cli_middle("Pre-resolution stage order")
        for item in stages:
            cli_info(f" {item.show()}")
        cli_div()

    cli_middle("Resolving dependencies...")
    unresolved_set = resolve_dependencies(stages)
    compute_transitive_deps(stages, unresolved_set)
    cli_middle()
    for item in stages:
        cli_info(f" {item.show_verbose()}")

    cli_div()
    cli_unresolved(unresolved_set)
    cli_div()

    sorted_groups = group_stages_by_build_order(stages, unresolved_set)

    cli_middle()
    cli_middle("Sorted groups by build order:")
    for group in sorted_groups:
        cli_middle(" Group:")
        for stage in group:
            cli_info(stage.show_verbose())
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
    
    colorama.init()
    main()
