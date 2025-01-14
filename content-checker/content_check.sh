#!/bin/bash

num_args=$#

if [[ $num_args -eq 0 ]]; then
if ! [[ -e "$path/config.yaml" ]]; then
cat << EOF
Usage: content_check.sh [ -P <path> ] [ -e | --episode <episode_name> ] [ -C | --challenges ] 
			[ -S | --solutions ] [ -D | --discussions ] [ -U <url> | --remote-url <url> ] 
			[ -o <file path> ] [ --help ]
EOF
exit 0
fi
fi

if [[ $1 == "--help" ]]; then
cat << EOF
Usage: content_check.sh [ -P <path> ] [ -e | --episode <episode_name> ] [ -C | --challenges ] 
			[ -S | --solutions ] [ -D | --discussions ] [ -U <url> | --remote-url <url> ] 
			[ -o <file path> ] [ --help ]

Will examine the content in a Lesson and makes sure that the episodes have fulfilled the requirements.

-P <path>
	Path to the Lesson Directory. Can either be an absolute or relative path based on where content_check.sh exists.
	Default value for the path is the current directory. It cannot be used in conjunction with the remote-url flag.
-e, --episode <episode_name>
	Must be used in conjunction with [-P <path>]. It will validate the specific episode passed through
-C, --challenges
	Outputs only the number of challenges in the episode
-S, --solutions
	Outputs only the number of solutions in the episode
-D, --discussions
	Outputs only the number of disucssions in the episode
-U <url> , --remote-url <url>
	Links to a remote GitHub repository and checks its content. It cannot be used in conjunction with the path flag.
-o <file path>
	Directs the output to the given file, outputs to the Terminal by default
-I 
	Open an interactive CLI, it is a standalone option
--help
	Outputs the manual
EOF
exit 0
fi

# Set everything to false 
challenge=1; solution=1; discussion=1; path=""; output="/dev/stdout"; remote=0;

for ((i=1; i<=$#; i++)); do
	if [ "${!i}" == "-C" ] || [ "${!i}" == "--challenges" ]; then
    	solution=0
		discussion=0
	elif [ "${!i}" == "-D" ] || [ "${!i}" == "--discussions" ]; then 
		challenge=0
		solution=0
	elif [ "${!i}" == "-S" ] || [ "${!i}" == "--solutions" ]; then
		challenge=0
		discussion=0
	elif [ "${!i}" == "-P" ]; then
		((i++))
		if [ -d ${!i} ]; then
			path="${!i}"
			((i--))
		else
			echo -e "Invalid path: ${!i}"
			exit 1
		fi
	elif [ "${!i}" == "-U" ] || [ "${!i}" == "--remote-url" ]; then
		((i++))
		remote_url="${!i}"
		folder_name=$(basename "$remote_url" .git)
		git clone --quiet "$remote_url" "$folder_name"
		path=${folder_name}
		remote=1
	elif [ "${!i}" == "-o" ]; then
		((i++))
		rm ${!i}
		touch ${!i}
		output=${!i}
		((i--))
	elif [ "${!i}" == "-I" ]; then
		python3 /Users/lawrencetlee/Personal/IMLS/imls-tools/content-checker/content_check_cli.py
	else
		if [[ $remote -eq 1 ]]; then
			rm -rf "${path}"
		fi
		cat << EOF
Usage: content_check.sh [ -P <path> ] [ -e | --episode <episode_name> ] [ -C | --challenges ] 
			[ -S | --solutions ] [ -D | --discussions ] [ -U <url> | --remote-url <url> ] 
			[ -o <file path> ] [ -I ] [ --help ]
EOF
exit 1
	fi
done


if [[ -n $path ]]; then
	path="${path}"
else
	path="./"
fi

# Scans config.yaml and validates it - Checks to see if you have filled in Title, Contact, Created, Source
Title=$(grep -E "title:" $path/config.yaml | awk -F "'" '{print $2}')
echo -e -e "Lesson Title: $Title" >> $output
echo -e -e "Config.yaml Validation:" >> $output
if [[ $Title = "Lesson Title" ]]; then echo -e "    Title: \033[31mMissing\033[0m" >> $output; else echo -e "    Title: \033[32m$Title\033[0m" >> $output; fi
contact=$(grep -E "contact:" $path/config.yaml | awk -F "'" '{print $2}')
if [[ $contact = "team@carpentries.org" ]]; then echo -e "    Contact: \033[31mInvalid\033[0m" >> $output; else echo -e "    Contact: \033[32m$contact\033[0m" >> $output; fi
created=$(grep -E "created: " $path/config.yaml | awk -F ": " '{print $2}')
if [[ -n $created ]]; then echo -e "    Created: \033[32m$created\033[0m" >> $output; else echo -e "    Created: \033[31mInvalid\033[0m" >> $output; fi
source=$(grep -E "source:" $path/config.yaml | awk -F "'" '{print $2}')
if [[ $source = "https://github.com/carpentries/workbench-template-md" ]]; then echo -e "    Source: \033[31mInvalid\033[0m" >> $output; else echo -e "    Source: \033[32m$source\033[0m" >> $output; fi


# Scans and Checks over the episodes, NON-Intrusive doesn't alter the episodes only reads
# Checks to see if there are questions, objectives, and keypoints that are required
echo -e -e "\nEpisode Validation:" >> $output
for file in "$path/episodes"/*; do
    if [ -f "$file" ]; then
		if [[ "$file" != *.md && "$file" != *.Rmd ]]; then
            continue
		fi

        episode_name="${file##*/episodes/}"

    	echo -e "	Episode: $episode_name" >> $output

		# Checks to see if they're questions and objs
		if grep -qE ":::.*questions" $file; then
			echo -e "		Questions: \033[32mValid\033[0m" >> $output
		else
			echo -e "		Questions: \033[31mInvalid\033[0m" >> $output
		fi
		if grep -qE ":::.*objectives" $file; then
			echo -e "		Objectives: \033[32mValid\033[0m" >> $output
		else
			echo -e "		Objectives: \033[31mInvalid\033[0m" >> $output
		fi
		
		# Checks to see if they're 
		if grep -qE ":::.*keypoints" $file; then
			echo -e "		Keypoints: \033[32mValid\033[0m" >> $output
		else
			echo -e "		Keypoints: \033[31mInvalid\033[0m" >> $output
		fi
		# Looks over solutions, challenges, and discussions - If solutions != challenges check over content
		if [ $solution -eq 1 ]; then
			num_sol=$(expr $(grep -cE ":::.*solution" $file) + 0)
			echo -e "		Number of Solutions: " $num_sol >> $output
		fi 
		if [ $challenge -eq 1 ]; then
			num_chal=$(expr $(grep -cE ":::.*challenge" $file) + 0)
			echo -e "		Number of Challenges: " $num_chal >> $output
		fi
		if [ $discussion -eq 1 ]; then
			num_disc=$(expr $(grep -cE ":::.*discussion" $file) + 0)
			echo -e "		Number of Discussions: " $num_disc >> $output
		fi
	fi
done

# If you decided to check over a remote repository it will delete the 
# remote repo from your directory
if [ $remote -eq 1 ]; then
	rm -rf ${path}
fi