from __future__ import print_function, unicode_literals
import os, re, tempfile, subprocess, shutil
import inquirer
from content_check import entireFolder, episodeFolder, configYaml, singleEpisode

def clear_screen():
    if os.name == 'nt':  # For Windows
        os.system('cls')
    else:                # For macOS and Linux
        os.system('clear')

def grep(pattern, file):
    with open(file, 'r') as f:
        lines = f.readlines()

    matched_lines = [line for line in lines if re.search(pattern, line)]

    return matched_lines

def local_lesson(cwd, local=True):
    clear_screen()

    if local:
        local_folders = [ name for name in os.listdir(cwd) if os.path.isdir(os.path.join(cwd, name)) ]
        local_folders.insert(0, "..")
        local_folders.insert(0, ".")
        prompt = f"Please navigate to the folder that contains your lesson. Once you are in the folder, please choose the '.' option. You are currently here: {cwd} "
        questions = [
            inquirer.List(
                "choice",
                message=prompt,
                choices=local_folders
            )
        ]

        answers = inquirer.prompt(questions)

        while answers["choice"] != ".":
            clear_screen()
            cwd = os.path.join(cwd, answers["choice"])
            os.chdir(cwd)
            local_folders = [ name for name in os.listdir(cwd) if os.path.isdir(os.path.join(cwd, name)) ]
            local_folders.insert(0, "..")
            local_folders.insert(0, ".")
            questions = [
                inquirer.List(
                    "choice",
                    message="Please navigate to the folder that contains your lesson. Once you are in the folder, please choose the '.' option.",
                    choices=local_folders
                )
            ]
            answers = inquirer.prompt(questions)
        
        local_files = os.listdir(cwd)

        if "CONTRIBUTING.md" not in local_files:
            print("Invalid Directory. Exiting with Status 1")
            exit(1)
        else:
            check = grep("Carpentry", os.path.join(cwd, "CONTRIBUTING.md"))
            if len(check) == 0:
                print("Invalid Directory. Exiting with Status 1")
                exit(1)
    else:
        os.chdir(cwd)
        local_files = os.listdir(cwd)
        if "CONTRIBUTING.md" not in local_files:
            print("Invalid Repository. Exiting with Status 1")
            return
        else:
            check = grep("Carpentry", os.path.join(cwd, "CONTRIBUTING.md"))
            if len(check) == 0:
                print("Invalid Repository. Exiting with Status 1")
                return

    clear_screen()
    questions = [
        inquirer.List(
            "check_flag",
            message="Please pick what you want to check. You can check the entire lesson or specific episodes or files",
            choices=["Everything", "All Episodes", "Single Episode", "config.yaml"],
        )
    ]
    answers = inquirer.prompt(questions)

    try:
        if answers["check_flag"] == "Everything":
            clear_screen()
            print(entireFolder(cwd))
        elif answers["check_flag"] == "All Episodes":
            clear_screen()
            print(episodeFolder(cwd))
        elif answers["check_flag"] == "Single Episode":
            clear_screen()
            episode_list = [name for name in os.listdir(os.path.join(cwd, "episodes"))]
            questions = [
            inquirer.List(
                "episode",
                message="Choose an episode to check.",
                choices=episode_list,
                )
            ]
            answers = inquirer.prompt(questions)
            while ".md" not in answers["episode"]:
                print("Invalid Episode. Episodes are markdown files with .md extension.")
                answers = inquirer.prompt(questions)
            clear_screen()
            print(singleEpisode(os.path.join(cwd, "episodes", answers["episode"]), answers["episode"]))
        else:
            clear_screen()
            print(configYaml(os.path.join(cwd, "config.yaml")))
    except Exception as e:
        print(e)


def remote_lesson():
    questions = [
        inquirer.Text(name='repo_url', message="Please type the url of the github repo"),
    ]
    
    answers = inquirer.prompt(questions)

    # Use case if string is empty
    if answers["repo_url"] == "":
        print("A url is required.")
        exit(1)
    
    # Check if the url is even a working url
    try:
        result = subprocess.run(["git", "ls-remote", answers["repo_url"]], capture_output=True)

        if result.returncode != 0:
            print("Invalid Github Repository URL.")
            exit(1)
        
        temp_dir = tempfile.mkdtemp()
        git_clone_command = ["git", "clone", answers["repo_url"], temp_dir]
        try:
            subprocess.run(git_clone_command, check=True, text=False)
            # Get the name of the folder
            local_lesson(temp_dir, False)
            shutil.rmtree(temp_dir)
        except:
            shutil.rmtree(temp_dir)
            print("Exit with an unknown failure upon cloning the repository.")

    except Exception as e:
        print(e)

def main():
    cwd = os.getcwd()
    clear_screen()
    questions = [
        inquirer.List(
            "choice",
            message="Welcome to Lesson Content Checker. Do you want to scan a local lesson or a remote lesson?",
            choices=["Local", "Remote"],
        ),
    ]

    answer = inquirer.prompt(questions)["choice"]
    if answer == "Local":
        local_lesson(cwd)
    else:
        remote_lesson()

if __name__ == "__main__":
    main()
