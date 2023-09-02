#!/bin/bash

num_args=$#

if [[ $num_args -eq 0 ]]; then
if ! [[ -e "$path/config.yaml" ]]; then
cat << EOF
Usage: content_check.sh [-P <path>] [ -e | --episode <episode_name> ] [ -C | --challenges ] 
			[ -S | --solutions ] [ -D | --discussions ] [-o <file>] [--help]
EOF
exit 0
fi
fi

if [[ $1 == "--help" ]]; then # FIXME add a manual
cat << EOF
Usage: content_check.sh [-P <path>] [ -e | --episode <episode_name> ] [ -C | --challenges ] 
			[ -S | --solutions ] [ -D | --discussions ]

Will examine the content in a Lesson and makes sure that the episodes have fulfilled the requirements.

-P <path>
	Path to the Lesson Directory. Can either be an absolute or relative path based on where content_check.sh exists.
	Default value for the path is the current directory.
-e, --episode <episode_name>
	Must be used in conjunction with [-P <path>]. It will validate the specific episode passed through
-C, --challenges
	Outputs the number of challenges in the episode
-S, --solutions
	Outputs the number of solutions in the episode
-D, --discussions
	Outputs the number of disucssions in the episode
--help
	Outputs the manual
-o <file>
	Directs the output to the given file, outputs to the Terminal by default
EOF
exit 0
fi

challenge=0; solution=0; discussion=0; path=""; output="/dev/stdout"

for ((i=1; i<=$#; i++)); do
	if [ "${!i}" == "-C" ] || [ "${!i}" == "--challenges" ]; then
    	challenge=1
	elif [ "${!i}" == "-D" ] || [ "${!i}" == "--discussions" ]; then 
		discussion=1
	elif [ "${!i}" == "-S" ] || [ "${!i}" == "--solutions" ]; then
		solution=1
	elif [ "${!i}" == "-P" ]; then
		((i++))
		if [ -d ${!i} ]; then
			path="${!i}"
			((i--))
		else
			echo "Invalid path: ${!i}"
			exit 1
		fi
	elif [ "${!i}" == "-o" ]; then
		((i++))
		rm ${!i}
		touch ${!i}
		output=${!i}
		((i--))
	fi
done


if [[ -n $path ]]; then
	path="${path}"
else
	path="./"
fi

# Scans config.yaml and validates it.
Title=$(grep -E "title:" $path/config.yaml | awk -F "'" '{print $2}')
echo -e "Lesson Title: $Title\n" >> $output
echo -e "Config.yaml Validation:" >> $output
if [[ $Title = "Lesson Title" ]]; then echo "    Title: Missing" >> $output; else echo "    Title: $Title" >> $output; fi
contact=$(grep -E "contact:" $path/config.yaml | awk -F "'" '{print $2}')
if [[ $contact = "team@carpentries.org" ]]; then echo "    Contact: Invalid" >> $output; else echo "    Contact: $contact" >> $output; fi
created=$(grep -E "created:" $path/config.yaml | awk -F "'" '{print $2}')
if [[ -n $created ]]; then echo "    Created: $created" >> $output; else echo "    Created: Invalid" >> $output; fi
source=$(grep -E "source:" $path/config.yaml | awk -F "'" '{print $2}')
if [[ $source = "https://github.com/carpentries/workbench-template-md" ]]; then echo "    Source: Invalid" >> $output; else echo "    Source: $source" >> $output; fi


# Scans and Checks over the episodes NON-Intrusive doesn't alter the episodes only reads
echo -e "\nEpisode Validation:" >> $output
for file in "$path/episodes"/*; do
    if [ -f "$file" ]; then
        episode_name="${file##*/episodes/}"

    	echo "	Episode: $episode_name" >> $output

		# Checks to see if they're questions and objs
		if grep -qE ":::.*questions" $file; then
			echo "		Questions: Valid" >> $output
		else
			echo "		Questions: Invalid" >> $output
		fi
		if grep -qE ":::.*objectives" $file; then
			echo "		Objectives: Valid" >> $output
		else
			echo "		Objectives: Invalid" >> $output
		fi
		
		# Checks to see if they're 
		if grep -qE ":::.*keypoints" $file; then
			echo "		Keypoints: Valid" >> $output
		else
			echo "		Keypoints: Invalid" >> $output
		fi

		if [ $solution -eq 1 ]; then
			num_sol=$(expr $(grep -cE ":::.*solution" $file) + 0)
			echo "		Number of Solutions: " $num_sol >> $output
		fi 
		if [ $challenge -eq 1 ]; then
			num_chal=$(expr $(grep -cE ":::.*challenge" $file) + 0)
			echo "		Number of Challenges: " $num_chal >> $output
		fi
		if [ $discussion -eq 1 ]; then
			num_disc=$(expr $(grep -cE ":::.*discussion" $file) + 0)
			echo "		Number of Discussions: " $num_disc >> $output
		fi
    fi
done