import argparse
import os
import re

# Existing utility functions

def grep(pattern, file):
    """
    Searches for lines matching the given regular expression pattern in the specified file.

    Args:
        pattern (str): The regular expression pattern to search for.
        file (str): The path to the file to search within.

    Returns:
        list: A list of lines from the file that match the pattern.
    """
    with open(file, 'r') as f:
        lines = f.readlines()

    matched_lines = [line for line in lines if re.search(pattern, line)]
    return matched_lines

def configYaml(filePath):
    """
    Validates the 'config.yaml' file by checking key fields like title, contact, created date, and source.

    Args:
        filePath (str): The path to the 'config.yaml' file.

    Returns:
        str: A formatted string that reports the validity of the key fields.
    """
    title = grep("title:", filePath)[0].split("'")[1]
    contact = grep("contact:", filePath)[0].split("'")[1]
    created = grep("created:", filePath)
    source = grep("source:", filePath)[0].split("'")[1]

    if "20" in created[0]:
        created = created[0].split(":")[1]
        created = created.split("\\n")[0]
    else:
        created = ""

    message = f"""Config.yaml Validation:
        Title: {title if title != "Lesson Title" else "Missing"}
        Contact: {contact if contact != "team@carpentries.org" else "Invalid"}
        Created: {created if created else "Invalid"}
        Source: {source if source != "https://github.com/carpentries/workbench-template-md" else "Invalid"}
    """

    return message

def episode_compile(filepath):
    """
    Checks an episode file for compile errors by ensuring that every callout block is correctly opened and closed.

    Args:
        filepath (str): The path to the episode file (Markdown or RMarkdown).

    Returns:
        tuple: A boolean indicating validity and a list of error messages if compile errors are found.
    """
    error = []
    valid = True
    stack = []
    def grep_line(pattern, file):
        matched_lines = []
        
        with open(file, 'r') as f:
            for line_number, line in enumerate(f, start=1):
                if re.search(pattern, line):
                    matched_lines.append([line_number, line.strip()])

        return matched_lines
    
    callout = grep_line(":::", filepath)

    for i in range(len(callout)):
        if callout[i][1].startswith("::: {.callout}"):
            stack.append(callout[i])
        elif callout[i][1] == ":::":  # Ending callout
            if stack:
                stack.pop()
            else:
                error.append(f"Unmatched callout end at line {callout[i][0]}")
                valid = False

    if stack:
        error.append(f"Unmatched callout start at line {stack[-1][0]}")
        valid = False

    return valid, error


def episodeFolder(filePath):
    """
    Checks all episode files in the specified folder for compile errors and the presence of key elements.

    Args:
        filePath (str): The path to the folder containing episode files.

    Returns:
        str: A report string indicating the status of each episode file.
    """
    episode_message = []
    message = ""
    try:
        file_list = os.listdir(filePath)
        for file_name in file_list:
            if ".md" in file_name or ".Rmd" in file_name:
                fullPath = os.path.join(filePath, f"{file_name}")
                episode_message.append(singleEpisode(fullPath, file_name))
        for m in episode_message:
            message += m
    except Exception as e:
        print(f"Error processing episode folder: {e}")
        return

    return message

def entireFolder(filePath):
    """
    Checks the entire lesson folder, including the 'config.yaml' file and all episode files in the 'episodes' directory.

    Args:
        filePath (str): The path to the lesson folder.

    Returns:
        str: A consolidated report string indicating the status of the config file and all episodes.
    """
    episode_dir = os.path.join(filePath, "episodes")
    config = os.path.join(filePath, "config.yaml")
    message = ""

    try:
        config_message = configYaml(config)
    except Exception as e:
        print(f"Error checking config.yaml: {e}")
        return
    episode_message = []
    try:
        file_list = os.listdir(episode_dir)
        for file_name in file_list:
            if ".md" in file_name or ".Rmd" in file_name:
                fullPath = os.path.join(episode_dir, f"{file_name}")
                episode_message.append(singleEpisode(fullPath, file_name))
        message = config_message
        for m in episode_message:
            message += m
    except Exception as e:
        print(f"Error processing episodes: {e}")
        return

    return message

def singleEpisode(filepath, episodeName):
    """
    Checks a single episode file for compile errors and other key elements like solutions, discussions, challenges, etc.

    Args:
        filepath (str): The path to the episode file.
        episodeName (str): The name of the episode.

    Returns:
        str: A report string indicating the status of the episode, including any compile errors or missing elements.
    """
    compile_error = episode_compile(filepath)
    if compile_error:
        message = f"""Episode: {episodeName}
        COMPILE ERROR"""
        for error in compile_error:
            message += f"""
                {error}"""
        return message

    solutions = grep(":::.*solution", filepath)
    discussions = grep(":::.*discussion", filepath)
    challenges = grep(":::.*challenge", filepath)
    objectives = grep(":::.*objective", filepath)
    questions = grep(":::.*question", filepath)
    keypoints = grep(":::.*keypoint", filepath)
    teaching_time = grep("teaching:", filepath)
    time = ""
    if teaching_time:
        for i in teaching_time[0]:
            if i.isdigit():
                time += i

    message=f"""Episode: {episodeName}
        Teaching Time: {time if teaching_time else "Missing"}
        Questions: {"Valid" if questions else "Invalid"}
        Objectives: {"Valid" if objectives else "Invalid"}
        Keypoints: {"Valid" if keypoints else "Invalid"}
        Number of Challenges: {len(challenges)}
        Number of Solutions: {len(solutions)}
        Number of Discussions: {len(discussions)}
    """

    return message

def main():
    parser = argparse.ArgumentParser(description="Carpentry Lesson Checker CLI Tool")
    parser.add_argument("lesson_folder", type=str, help="Path to the lesson folder")
    parser.add_argument("--validate-config", action="store_true", help="Validate the config.yaml file")
    parser.add_argument("--check-episodes", action="store_true", help="Check episodes for compile errors")
    parser.add_argument("--check-entire-folder", action="store_true", help="Check the entire folder for compile errors and config validation")
    parser.add_argument("--check-episode-folder", action="store_true", help="Check a folder containing episodes for specific content")

    args = parser.parse_args()

    # If no specific arguments are provided, run all checks
    if not (args.validate_config or args.check_episodes or args.check_entire_folder or args.check_episode_folder):
        args.validate_config = True
        args.check_episodes = True
        args.check_entire_folder = True
        args.check_episode_folder = True

    # Run the specified checks (or all checks if no arguments were passed)
    if args.validate_config:
        config_file = os.path.join(args.lesson_folder, "config.yaml")
        if os.path.exists(config_file):
            message = configYaml(config_file)
            print(message)
        else:
            print("Config.yaml not found in the selected folder.")

    if args.check_episodes:
        episode_folder = args.lesson_folder
        if os.path.exists(episode_folder):
            for filename in os.listdir(episode_folder):
                if filename.endswith(".md"):
                    valid, errors = episode_compile(os.path.join(episode_folder, filename))
                    if not valid:
                        print(f"Errors found in {filename}:\n" + "\n".join(errors))
                    else:
                        print(f"No errors found in {filename}.")
        else:
            print("Selected folder does not exist or contains no episode files.")

    if args.check_entire_folder:
        message = entireFolder(args.lesson_folder)
        if message:
            print(message)

    if args.check_episode_folder:
        message = episodeFolder(args.lesson_folder)
        if message:
            print(message)

if __name__ == "__main__":
    main()
