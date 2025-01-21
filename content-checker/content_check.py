# import PySimpleGUI as sg
import os, re

######################### GLOBAL VARIABLES #########################
processing = False
folder_clicked = False
filepath=""
temp_dir = None
################################################################

######################### DEFINE GREP #########################
def grep(pattern, file):
    with open(file, 'r') as f:
        lines = f.readlines()

    matched_lines = [line for line in lines if re.search(pattern, line)]

    return matched_lines
################################################################

# ######################### DATA PARSING #########################
# VALIDATES THE CONFIG.YAML
def configYaml(filePath):
    # print(os.path.abspath(filePath))

    title = grep("title:", filePath)[0].split("'")[1]
    contact = grep("contact:", filePath)[0].split("'")[1]
    created = grep("created:", filePath)
    source = grep("source:", filePath)[0].split("'")[1]

    if "20" in created[0]:
        created = created[0].split(":")[1]
        created = created.split("\n")[0]
    else:
        created = ""

    message =f"""Config.yaml Validation:
        Title: {f"\033[32m{title}\033[0m" if title != "Lesson Title" else "\033[31mMissing\033[0m"}
        Contact: {f"\033[32m{contact}\033[0m" if contact != "team@carpentries.org" else "\033[31mInvalid\033[0m"}
        Created: {f"\033[32m{created}\033[0m" if created else "\033[31mInvalid\033[0m"}
        Source: {f"\033[32m{source}\033[0m" if source != "https://github.com/carpentries/workbench-template-md" else "\033[31mInvalid\033[0m"}
    """

    return message

# CHECK EPISODE FOR COMPILE ERRORS
def episode_compile(filepath):
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
        callout_block = ""
        for j in range(len(callout[i][1])):
            if callout[i][1][j].isalpha():
                callout_block += callout[i][1][j]
        callout[i][1] = callout_block

    for i in callout:
        if i[1]:
            stack.append(i)
        else:
            if not stack:
                error.append(f"Extraneous closing :::, Line {i[0]}")
                valid = False
                continue
            stack.pop()

    if stack or not valid:
        for i in stack:
            error.append(f"{i[1].upper()} missing closing :::, Line {i[0]}")

    return error

# SCANS THROUGH EPISODE
def singleEpisode(filepath, episodeName):
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
        Questions: {"\033[32mValid\033[0m" if questions else "\033[31mInvalid\033[0m"}
        Objectives: {"\033[32mValid\033[0m" if objectives else "\033[31mInvalid\033[0m"}
        Keypoints: {"\033[32mValid\033[0m" if keypoints else "\033[31mInvalid\033[0m"}
        Number of Challenges: {len(challenges)}
        Number of Solutions: {len(solutions)}
        Number of Discussions: {len(discussions)}
    """

    return message

def entireFolder(filePath):
    episode_dir = os.path.join(filePath, "episodes")
    config = os.path.join(filePath, "config.yaml")
    message =""

    try:
        config_message = configYaml(config)
    except:
        return
    episode_message = []
    try:
        file_list = os.listdir(episode_dir)
        # print(file_list)
        for file_name in file_list:
            if ".md" in file_name or ".Rmd" in file_name:
                fullPath = os.path.join(episode_dir, f"{file_name}")
                episode_message.append(singleEpisode(fullPath, file_name))
        message = config_message
        for m in episode_message:
            message += m
    except:
        return

    

    return message

def episodeFolder(filePath):
    episode_message = []
    message = ""
    try:
        file_list = os.listdir(filePath)
        # print(file_list)
        for file_name in file_list:
            if ".md" in file_name or ".Rmd" in file_name:
                fullPath = os.path.join(filePath, f"{file_name}")
                episode_message.append(singleEpisode(fullPath, file_name))
        message = ""
        for m in episode_message:
            message += m
    except:
        # print("WTF 2")
        return

    return message
################################################################