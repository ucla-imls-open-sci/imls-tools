from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import Chroma
from langchain_community import embeddings
from langchain_community.chat_models import ChatOllama
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain.text_splitter import CharacterTextSplitter

model_local = ChatOllama(model="mistral")

# Chunking Data
urls = [
    'https://carpentries.github.io/sandpaper-docs/',
    'https://docs.carpentries.org/topic_folders/communications/resources/style-guide.html',
    'https://carpentries.github.io/sandpaper-docs/episodes.html'
]

docs = [WebBaseLoader(url).load() for url in urls]
docs_list = [item for sublist in docs for item in sublist]
text_splitter = CharacterTextSplitter.from_tiktoken_encoder(chunk_size=7500, chunk_overlap=100)
doc_splits = text_splitter.split_documents(docs_list)

# Convert into embeddings
vectorstore = Chroma.from_documents(
    documents=doc_splits,
    collection_name="rag-chroma",
    embedding=embeddings.OllamaEmbeddings(model='nomic-embed-text'),
)
retriever = vectorstore.as_retriever()

after_rag_template = """Answer the question based only on the following context:
{context}
Questions: {question}"""
after_rag_prompt = ChatPromptTemplate.from_template(after_rag_template)
after_rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | after_rag_prompt
    | model_local
    | StrOutputParser()
)

print(after_rag_chain.invoke("""Does the following episode follow the Carpentries Episode Structure?
---
title: 'Working with Open Science Team Agreement'
teaching: 5
exercises: 15
---

:::::::::::::::::::::::::::::::::::::: questions 

- How do you access and edit the team agreement?
- How do you use it for an example domain?

::::::::::::::::::::::::::::::::::::::::::::::::

::::::::::::::::::::::::::::::::::::: objectives

- Download the Team Agreement from Zenodo
- Locate an appropriate subject data repository for an example research group
- Edit the Team Agreement

::::::::::::::::::::::::::::::::::::::::::::::::

## Accessing the Open Science Team Agreement

The Open Science Team Agreements are available from Zenodo at https://zenodo.org/record/7154100. On this page you will find versions for Word, Google Doc, Overleaf, and plain text. We recommend that researchers save a project-specific copy to modify - don't forget to give it a good file name! 


::::::::::::::::::::::::::::::::::::: challenge 

## Exploring the Agreement (10 min) 

Group Discussion or Think-Pair-Share

Go to Zenodo and download a copy of the [Open Science Team Agreement](https://zenodo.org/record/7154100) on the platform of your choice. 

Skim the content of the agreements. Which of these are topics that you regularly discuss with researchers and which ones are new to you? Which of these areas are more familiar to researchers you work with?

Jot down a couple of notes and we will discuss as a group.

:::::::::::::::::::::::::::::::::::::::

## Customizing the Team Agreement
It can be helpful to think how a particular research team might customize the agreements for their workflows. Let’s practice customizing the Open Science Team agreements for an example team.

**Case Study - Dr. Sheri Lee (Fictional)** 

Dr. Sheri Lee is a clinical researcher at UC San Francisco working on the link between lung cancer and pollution. She collects clinical data from the Electronic Health Record (EHR) and also gathers data via patient questionnaires. Her team consists of herself, one clinical research coordinator, and two graduate students, and she is committed to giving credit to their work. She shares her preprints on MedRxiv, and her data in the Vivli clinical repository. She doesn’t currently share her postprints, or routinely share slides or her analysis code.

::::::::::::::::::::::::::::::::::::: challenge 

## Customizing the Agreement for Dr. Lee (10 min)

You are meeting with Dr. Lee this week to talk about Open Science practices. Make two edits to the Open Science Team Agreement based on what you currently know about Dr. Lee’s workflow to customize it for this team. In addition, what is one suggestion you have for a new practice they might try?

Share the edits you made with the class and provide your rationale.

:::::::::::::::::::::::: solution 

## Ideas for edits 

Possible edits to the Open Science Team Agreement based on current practices include: 

- Adding MedRxiv to the preprints section
- Familiarizing team members with CREDIT system to formalize author contributions
- Designating Vivli as their data repository 

Ideas for edits for new practices to introduce

 - Code in Zenodo
 - Postprints in her institutional repository
 - Upload presentation slides to her institutional repository


:::::::::::::::::::::::::::::::::
::::::::::::::::::::::::::::::::::::::::::::::::

## Showcasing the Team Agreement
Researchers are encouraged to share their completed Open Science Team Agreement by uploading it to Zenodo and using the hashtag #openscienceteamagreement so that others can find it.


::::::::::::::::::::::::::::::::::::: keypoints 

- You access and edit the Team Agreement by visiting the Zenodo page, where you can find editable versions for Word, Google Doc, Overleaf, and plain text. 
- You can modify the highlighted yellow sections of the Team Agreement to suit your needs and delete any sections that are irrelevant to your domain. For example, you could list a subject specific repository where research outputs will be stored. 

::::::::::::::::::::::::::::::::::::::::::::::::
"""))

# OUTPUT:
#  The episode provided follows the Carpentries Episode Structure to some extent, but there are a few differences compared to the examples given in the Style Guide:

# - There is no 'prerequisites' section, although it might be helpful to mention any necessary software or tools needed for the exercises.
# - The objectives are listed under a separate heading instead of being integrated into the questions section as bullet points. However, they follow the same structure as shown in the Style Guide examples.
# - The episode provides case studies and challenges, which can be considered as interactive elements, but there is no explicit 'assessment' or 'solution' section like in the examples provided. Instead, solutions are presented together with the challenge for Dr. Lee's team.
# - There is a 'Keypoints' section at the end of the episode that summarizes key takeaways from the exercises and discussion.

# Overall, this episode is well-structured and easy to follow, providing clear instructions on accessing, customizing, and using the Open Science Team Agreement. The interactive elements help engage learners and facilitate group discussions and active learning.