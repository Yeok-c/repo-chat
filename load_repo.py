from git import Repo
from langchain.text_splitter import Language
from langchain.document_loaders.generic import GenericLoader
from langchain.document_loaders.parsers import LanguageParser        
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationSummaryMemory
from langchain.chains import ConversationalRetrievalChain
# import tiktoken
from langchain.callbacks import get_openai_callback


class RepoLoader():
    def __init__(self, codebase_path: str, model_name="gpt-3.5-turbo-16k-0603", suffixes=[".py"]):                
        self.model_name = model_name
        self.cb = None

        if "github.com" in codebase_path:
            print("Cloning repo...")
            codebase_local_path = "./repo"
            repo = Repo.clone_from(codebase_path, to_path=codebase_local_path)
            codebase_path = codebase_local_path
        else:
            print("Loading from local repo...")
        
        # Load
        loader = GenericLoader.from_filesystem(
            codebase_path,
            glob="**/*",
            suffixes=suffixes,
            parser=LanguageParser(language=Language.PYTHON, parser_threshold=500)
        )
        documents = loader.load()
        # len(documents)

        python_splitter = RecursiveCharacterTextSplitter.from_language(language=Language.PYTHON, 
                                                                    chunk_size=2000, 
                                                                    chunk_overlap=200,)
        texts = python_splitter.split_documents(documents)
        len(texts)

        with get_openai_callback() as cb:
            # Set up chroma db and retriever
            db = Chroma.from_documents(texts, OpenAIEmbeddings(disallowed_special=()))
            retriever = db.as_retriever(
                search_type="mmr",  # Also test "similarity"
                search_kwargs={"k": 8},
            )

            # Set up LLM with memory
            llm = ChatOpenAI(model_name=self.model_name) 
            memory = ConversationSummaryMemory(llm=llm,memory_key="chat_history",return_messages=True)
            self.qa = ConversationalRetrievalChain.from_llm(llm, retriever=retriever, memory=memory)
        
        print(f'Setting up codebase used {cb}')
        self.update_usage(cb)
        
    def update_usage(self, cb):
        if self.cb is None:
            self.cb = cb
            return
        else:
            self.cb.total_tokens += cb.total_tokens
            self.cb.prompt_tokens += cb.prompt_tokens
            self.cb.completion_tokens += cb.completion_tokens
            self.cb.total_cost += cb.total_cost

    def chat(self, question):
        with get_openai_callback() as cb:
            result = self.qa(question)

        self.update_usage(cb)

        return result['answer']

if __name__ == "__main__":
    repoloader = RepoLoader(
        codebase_path="https://github.com/Yeok-c/Stewart_Py"
        # model_name="gpt-3.5-turbo", # default
        # suffixes=[".py"]  # default
        )
    
    try:
        while True:
            question = input("Input: ")
            answer = repoloader.chat(question)
            print("Output: " + answer)
            print("\n")

    
    except KeyboardInterrupt:
        print(' \nExiting program')
        print(f'Total tokens: {repoloader.cb.total_tokens}')
        print(f'Prompt tokens: {repoloader.cb.prompt_tokens}')
        print(f'Completion tokens: {repoloader.cb.completion_tokens}')
        print(f'Total cost: {repoloader.cb.total_cost}')
        