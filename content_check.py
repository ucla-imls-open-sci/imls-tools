import PySimpleGUI as sg
import string, sys, os, time, re
import subprocess, tempfile, shutil

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
        Title: {title if title != "Lesson Title" else "Missing"}
        Contact: {contact if contact != "team@carpentries.org" else "Invalid"}
        Created: {created if created else "Invalid"}
        Source: {source if source != "https://github.com/carpentries/workbench-template-md" else "Invalid"}
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
        Questions: {"Valid" if questions else "Invalid"}
        Objectives: {"Valid" if objectives else "Invalid"}
        Keypoints: {"Valid" if keypoints else "Invalid"}
        Number of Challenges: {len(challenges)}
        Number of Solutions: {len(solutions)}
        Number of Discussions: {len(discussions)}
    """

    return message

def entireFolder(filePath):
    # print(filePath)
    episode_dir = os.path.join(filePath, "episodes")
    config = os.path.join(filePath, "config.yaml")
    message =""
    # print(f"Config Path: {config}")
    # print(f"Episode Path: {episode_dir}")

    try:
        config_message = configYaml(config)
        # print(config_message)
    except:
        # print("WTF 1")
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
        # print("WTF 2")
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


######################### USER INTERFACE #########################
# First window that allows you to select your folder
file_list_column = [
    [
        sg.Text("Lesson Folder", font=(24)),
        sg.In(size=(40, 1), enable_events=True, key="-ROOT FOLDER-"),
        sg.FolderBrowse(font=(24)),
        sg.Button("Remote Repo", enable_events=True, key="-REMOTE-", font=(24)),
    ],
    [
        sg.Listbox(values=[], enable_events=True, size=(60, 20), key="-FILE LIST-", font=(24))
    ],
    [
        sg.Column([
        [
            sg.Button("", enable_events=folder_clicked, key="-OPEN FOLDER-", font=(24), size=(9,1))
        ],]),
        sg.Column([
        [
            sg.Button("Run", enable_events=True, key="-RUN-", font=(24))
        ],]),
        sg.Column([
        [
            sg.Button("Clear", enable_events=True, key="-CLEAR-", font=(24))
        ],])
    ]
    
]

# Second Window Displaying Results
results_window = [[
    sg.Frame("Results Window", 
    layout=[
        [sg.Multiline("", background_color = "white", 
        text_color="black", key="-FRAME TEXT-", font=(20), size = (550,400)
        )],

    ], 
    element_justification="left", size=(550, 400), background_color="white", 
    title_color="black", font=(40),
    )],        
]


# ----- Full layout -----
layout = [
    [
        sg.Column(file_list_column),
        sg.VSeparator(),
        sg.Column(results_window),
    ]
]

def repo_popup():
    global temp_dir

    # ----- Popup layout -----
    layout_popup = [
        [sg.Text("Enter the Repository's URL:", font=(24))],
        [sg.In(size=(40, 1), enable_events=True, key="-REPO-", font=(24))],
        [
            sg.Column([
                [sg.Button('Search', key="-SEARCH-", enable_events=True, font=(24))],
            ]),
            sg.Column([
                [sg.Button('Close', key="-CLOSE-", font=(24), enable_events=True)]
            ]),
        ]
    ]

    window_popup = sg.Window('Repository Search', layout_popup)

    while True:
        event_popup, values_popup = window_popup.read()
        if event_popup == sg.WIN_CLOSED or event_popup == 'Close Popup':
            window_popup.close()
            window_popup = None
            break
        elif event_popup == "-CLOSE-":
            window_popup.close()
            window_popup = None
            break
        elif event_popup == "-SEARCH-":
            try:
                # Create the Temporary Directory:
                if temp_dir is None:
                    temp_dir = tempfile.mkdtemp()
                    print(temp_dir)
                else:
                    shutil.rmtree(temp_dir)
                    temp_dir = None
                    temp_dir = tempfile.mkdtemp()
                    print(temp_dir)
                repo_url = values_popup['-REPO-']
                git_clone_command = ['git', 'clone', repo_url, temp_dir]
                try:
                    subprocess.run(git_clone_command,
                                    check=True, text=True)
                    print(f"Repository cloned to {temp_dir}")
                    filepath = temp_dir
                    window["-ROOT FOLDER-"].update(filepath)
                    try:
                    # Get list of files in folder
                        file_list = os.listdir(filepath)
                        file_list.insert(0, "..")
                    except:
                        file_list = []

                    fnames = [
                        f for f in file_list
                    ]
                    window["-FILE LIST-"].update(fnames)
                    window_popup.close()
                except subprocess.CalledProcessError as e:
                    print(f"Error: {e}")
                    sg.popup_error("This is an INVALID repository", title="Invalid Repository", font=(100))

            except:
                shutil.rmtree(temp_dir)

# ----- Create Windows -----
window = sg.Window("Lesson Checker", layout, size=(1000, 500))

# Run the Event Loop
while True:
    event, values = window.read()
    if event == "Exit" or event == sg.WIN_CLOSED:
        break
    # Folder name was filled in, make a list of files in the folder
    if event == "-ROOT FOLDER-":
        folder = values["-ROOT FOLDER-"]
        try:
            # Get list of files in folder
            file_list = os.listdir(folder)
            file_list.insert(0,"..")
        except:
            file_list = []

        fnames = [
            f for f in file_list
        ]
        window["-FILE LIST-"].update(fnames)

    elif event == "-FILE LIST-":  # A file was chosen from the listbox
        try:
            # print(values["-FILE LIST-"])
            # Gets the filepath to the file that you clicked on
            filepath = os.path.join(
                values["-ROOT FOLDER-"], values["-FILE LIST-"][0]
            )
            
            if os.path.isdir(filepath):
                window["-OPEN FOLDER-"].update("Open Folder")
                folder_clicked = True
            else:
                window["-OPEN FOLDER-"].update("")
                folder_clicked = False
        except:
            pass


    elif event == "-RUN-":
        # processing = True
        if not values["-FILE LIST-"]: # RUN IT ON THE ENTIRE DIRECTORY
            if not os.path.isdir(values["-ROOT FOLDER-"]):
                sg.popup_error("This is an INVALID directory", title="Invalid Directory", font=(100))
            file_list = os.listdir(values["-ROOT FOLDER-"])
            if "episodes" not in file_list or "config.yaml" not in file_list:
                sg.popup_error("This is an INVALID directory", title="Invalid Directory", font=(100))
            else:
                # message = 
                window["-FRAME TEXT-"].update(entireFolder(values["-ROOT FOLDER-"]))
                # print(values["-ROOT FOLDER-"])

        else: # RUN IT ON THE FILE/FOLDER THAT WAS CLICKED
            # print("FILE CLICKED") #FIXME
            # if os.path.isdir()
            # print(filepath)
            # OPTION 1 Run Check on the entire Directory Highlighted
            if os.path.isdir(filepath) and "/episodes" not in filepath:
                file_list = os.listdir(filepath)
                if "config.yaml" and "episodes" not in file_list:
                    sg.popup_error("This is an INVALID directory! Choose A different directory.", 
                    title="Invalid Directory", font=(100))
                else:
                    window["-FRAME TEXT-"].update(entireFolder(filepath))
            
            # OPTION 2 Run Check on Config.yaml
            elif "config.yaml" in filepath:
                window["-FRAME TEXT-"].update(configYaml(filepath))

            # OPTION 3 Run Check on a single Episode
            elif "episodes/" in filepath:
                window["-FRAME TEXT-"].update(singleEpisode(filepath, values["-FILE LIST-"][0]))

            # OPTION 4 Run Check on the entire Episodes Folder
            elif re.search("/episodes", filepath):
                window["-FRAME TEXT-"].update(episodeFolder(filepath))
            
            else:
                sg.popup_error("This is an INVALID file/directory! Choose A different file/directory.", 
                title="Invalid File/Folder", font=(100))

        # processing = False
    
    elif event == "-OPEN FOLDER-":
        if folder_clicked:
            if ".." in filepath:
                filepath = os.path.abspath(filepath)
            window["-ROOT FOLDER-"].update(filepath)
            try:
                # Get list of files in folder
                file_list = os.listdir(filepath)
                file_list.insert(0, "..")
            except:
                file_list = []

            fnames = [
                f for f in file_list
            ]
            window["-FILE LIST-"].update(fnames)
        
    elif event == "-CLEAR-":
        window["-FRAME TEXT-"].update("")
    
    elif event == "-REMOTE-":
        repo_popup()
        
# print(temp_dir)
if temp_dir is not None:
    shutil.rmtree(temp_dir)

window.close()

################################################################