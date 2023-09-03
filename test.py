import PySimpleGUI as sg
import subprocess, tempfile, shutil

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
                except subprocess.CalledProcessError as e:
                    print(temp_dir)
                    print(f"Error: {e}")
            except:
                print(temp_dir)
                shutil.rmtree(temp_dir)