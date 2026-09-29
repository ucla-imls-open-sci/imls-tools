# The Carpentries Lab reviewer checklist

Source: https://github.com/carpentries-lab/reviews/blob/main/docs/reviewer_guide.md
Retrieved: 2026-09-29 by scripts/refresh_rubric.py. Edit by re-running the script, not by hand.

[This checklist is available as a template for you to use when preparing your review to post to the issue thread](./templates/review_template.md).

### Accessibility
- [ ] The alternative text of all figures is accurate and sufficiently detailed *.
  - Large and/or complex figures may not be described completely in the alt text of the image and instead be described elsewhere in the main body of the episode.
- [ ] The lesson content does not make extensive use of colloquialisms, region- or culture-specific references, or idioms.
- [ ] The lesson content does not make extensive use of contractions (“can’t” instead of “cannot”, “we’ve” instead of “we have”, etc).

\* To view the alternative text of an image, we recommend using
[the WAVE Web Accessibility Evaluation Tool][wave] or associated browser extensions.
You can also _inspect_ the source HTML of the image element in the developer tools of your web browser,
or consult the source (R)Markdown file for the relevant page in the lesson repository on GitHub.
For more information about what makes good alternative text for an image,
read [How to Design Great Alt Text: An Introduction][deque-alt-text],
and [Writing Alt Text for Data Visualization][alt-text-data]


### Content

- The lesson content:
    - [ ] conforms to [The Carpentries Code of Conduct][code-of-conduct].
    - [ ] meets the objectives defined by the authors.
    - [ ] is appropriate for the target audience identified for the lesson.
    - [ ] is accurate.
    - [ ] is descriptive and easy to understand.
    - [ ] is appropriately structured to manage cognitive load.
    - [ ] does not use dismissive language.
- [ ] Tools used in the lesson are open source or, where tools used are closed source/proprietary, there is a good reason for this e.g. no open source alternatives are available or widely-used in the lesson domain.
- [ ] Any example data sets used in the lesson are accessible, well-described, available under a CC0 license, and representative of data typically encountered in the domain.
- [ ] The lesson does not make use of superfluous data sets, e.g. increasing cognitive load for learners by introducing a new data set instead of reusing another that is already present in the lesson.
- [ ] The example tasks and narrative of the lesson are appropriate and realistic.
- [ ] The solutions to all exercises are accurate and sufficiently explained.
- [ ] Any discussion exercises without solutions are accompanied by sufficient information/guidance so that Instructors can judge whether the discussion's learning objectives have been met.
- [ ] The lesson includes exercises in a variety of formats.
- [ ] Exercise tasks and formats are appropriate for the expected experience level of the target audience.
- [ ] All lesson and episode objectives are assessed by exercises or another opportunity for formative assessment.
- [ ] Exercises are designed with diagnostic power.

### Design

- [ ] Learning objectives for the lesson and its episodes are clear, descriptive, and measurable. They focus on the skills being taught and not the functions/tools e.g. “filter the rows of a data frame based on the contents of one or more columns,” rather than “use the filter function on a data frame.”
- [ ] The target audience identified for the lesson is specific and realistic.

### Supporting information

- [ ] The list of required prior skills and/or knowledge is complete and accurate.
- [ ] The setup and installation instructions are complete, accurate, and easy to follow.
- [ ] No key terms are missing from the lesson glossary or are not linked to definitions in an external glossary e.g. [Glosario][glosario].

[alt-text-data]: https://medium.com/nightingale/writing-alt-text-for-data-visualization-2a218ef43f81
[code-of-conduct]: https://docs.carpentries.org/policies/coc/
[deque-alt-text]: https://www.deque.com/blog/great-alt-text-introduction/
[glosario]: https://carpentries.github.io/glosario/
[wave]: https://wave.webaim.org/
