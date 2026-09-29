# Carpentries Workbench documentation (excerpts)

Source: https://carpentries.github.io/sandpaper-docs/episodes.html
Retrieved: 2026-09-29 by scripts/refresh_rubric.py. Edit by re-running the script, not by hand.

## Required Elements

To keep with our active learning principles, we want to be mindful about the content we present to the learners. We need to give them a clear title, questions and objectives, and an estimate of how long it will take to navigate the episode (though this latter point has shown to be demoralizing). Finally, at the end of the episode, we should reinforce the learners’ progress with a summary of key points.


### YAML metadata

The YAML syntax of an episode contains three elements of metadata associated with the episode at the very top of the file:


### YAML


### Questions, Objectives, Keypoints

These are three blocks that live at the top and bottom of the episodes.

- questions are displayed at the beginning of the episode to prime the learner for the content
- objectives are the learning objectives for an episode and are displayed along with the questions
- keypoints are displayed at the end of the episode to reinforce the objectives
They are formatted as pandoc fenced divisions , which we will explain in the next section :


### MARKDOWN

## Exercises/Challenges

The method of creating callout blocks with fences can help us create solution blocks nested within challenge blocks. Much like a toast sandwich , we can layer blocks inside blocks by adding more layers. For example, here’s how I would create a single challenge and a single solution:


### MARKDOWN

To add more content to the challenge, you close the first solution and add more text:

Now, here’s a real challenge for you


### Use Spoilers Instead of Floating Solution Blocks

When not attached to a challenge div, a formatted solution block will be displayed with too much “buoyancy” i.e. floating too high and obscuring some of the preceding content.

To avoid this, use the spoiler class of fenced div for expandable/collapsible blocks of details instead of a floating solution .
