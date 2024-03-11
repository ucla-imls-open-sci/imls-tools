# Content Check Scripts

There are two content check scripts in this repository. content_check.sh and content_check.py. Both scripts do the same thing except the
python script has a gui that is easy to navigate.

## content_check.py

To run this script you need python3 installed. This script was written on python3.11. You will need to install the following packages:
```
pip install pysimplegui
```

Once you install the package, you can run the script with
```
python3 content_check.py
```
You have the option to validate a single episode, the episode folder, the config.yaml, the entire repository. You can do this by either navigating to the file/folder containing what you wan to validate or by clicking on the `Remote Repo` button.

## content_check.sh
Has the same functionality as content_check.py. Make sure you have given the script execution permissions. You can do this with the following command in your terminal `chmod +x content_check.sh`.
You can see the comprehensive list of commands by running the following shell command:
```
./content_check.sh --help
```
The most basic and general case is the following:
```
./content_check.sh -U <remote github url>
```
This will scan over the contents in the github url.