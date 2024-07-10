import os
from flask_socketio import emit
from langchain import embeddings
from langchain.embeddings import OpenAIEmbeddings
from langchain.prompts.prompt import PromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.chains.conversational_retrieval.prompts import CONDENSE_QUESTION_PROMPT
from langchain.chains.question_answering import load_qa_chain
from langchain.chains.llm import LLMChain
from langchain.llms import OpenAI
from langchain.callbacks.manager import CallbackManager
from langchain.vectorstores import Milvus
os.environ['OPENAI_API_KEY'] = ''
os.environ["OPENAI_API_BASE"] = ''
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
question_dict = {'西方经济学习题集': "question_set_01"}
question_dict2 = {'question_set_01': "西方经济学习题集"}
class ChainStreamHandler(StreamingStdOutCallbackHandler):

    def __init__(self, response_name):
        super().__init__()
        #self.gen = gen
        self.response_name = response_name

    def on_llm_new_token(self, token: str, **kwargs):

        if token:

            emit(self.response_name, {'token': token})

        else:

            emit(self.response_name, {'token': 'finished'})



def return_source(result,collection_name):

    source_documents = result['source_documents']
    docs = []
    source = ''
    if(collection_name == "enocmics_book"):

        for doc in source_documents:
            docs.append(doc.metadata['article_source'])
        docs = list(set(docs))
        source += '\n知识来源: \n'
        for doc in docs:
            doc = doc + '\n'
            source += doc

    elif(collection_name == "economics_questions"):

        for doc in source_documents:

            book_fake_name = question_dict2[doc.metadata['question_book']]

            docs.append(book_fake_name)

        docs = list(set(docs))
        source += '\n知识来源: \n'
        for doc in docs:
            doc = doc + '\n'
            source += doc
    else:
        source ='\n知识来源: \n' + "没有找到相关的参考资料"
    return source

def llm_chain(collection_name, template, vectorstore, k, book_name):

    if(collection_name == "enocmics_book"):
        response_name = "article-support"
        expr = f"article_key=='{book_name}'"
    elif(collection_name == "economics_questions"):
        response_name = "question-support"
        book_name=question_dict[book_name]
        expr = f"question_book=='{book_name}'"

    PROMPT = PromptTemplate(template=template, input_variables=["question", "context"])

    question_llm = OpenAI(temperature=0)

    streaming_llm = ChatOpenAI(
        model="gpt-3.5-turbo-0125",
        verbose=True,
        streaming=True,
        callback_manager=CallbackManager([ChainStreamHandler(response_name)]),
        temperature=0.2, max_tokens=4000
    )

    question_generator = LLMChain(llm=question_llm, prompt=CONDENSE_QUESTION_PROMPT)
    doc_chain = load_qa_chain(llm=streaming_llm, chain_type="stuff", prompt=PROMPT)

    qa = ConversationalRetrievalChain(retriever=vectorstore.as_retriever(search_kwargs={"k": k,'expr':expr}),
                                      combine_docs_chain=doc_chain,
                                      question_generator=question_generator,
                                      return_source_documents=True, max_tokens_limit=4000)
    return qa



def llm_preparation(data, collection_name):

    message = data['message']
    language = data['language']
    book_name = data['book']
    if(collection_name == "enocmics_book"):
        store = Milvus(
            embeddings,
            collection_name=collection_name,
            connection_args={
                "host": "",
                "port": "19530",
                "user": '',
                "db_name": "economics",
                "password": ''},
            primary_field="id",
            text_field="article_text",
            vector_field="article_vector"
        )

    elif(collection_name == "economics_questions"):
        store = Milvus(
            embeddings,
            collection_name=collection_name,
            connection_args={
                "host": "",
                "port": "19530",
                "user": '',
                "db_name": "",
                "password": ''},
            primary_field="id",
            text_field="question_answer_explanation",
            vector_field="question_vector"
        )
    return store, message, language, book_name


def llm_thread(data, collection_name):

    language_dict = {'en-us': "English", 'zh-cn': "中文"}

    vectorstore, question, language, book_name = llm_preparation(data, collection_name)

    language_name = language_dict[language]

    set_language = f"请你必须使用{language_name}进行回答."

    template1 = """
    作为大学新聘任的宏观经济学老师，我致力于回答与宏观经济学相关的学生提问。请参照以下指引以确保您的问题得到妥善回答：

        提问依据：我将依据您提供的上下文（context）来回答问题。请确保上下文与宏观经济学相关，以便我能提供准确的解答。

        知识补充：如果提供的上下文不足以回答您的问题，我将基于我的专业知识进行回答。

        难度判断：面对复杂的问题，如果我暂时无法提供答案，我会诚实回复“这个问题有点难度，我先去学习一下”，以保证信息的准确性。

        专业范围：我专注于宏观经济学领域的问题。如遇到非宏观经济学相关的问题，我将回答：“对不起，我是一个宏观经济学老师，无法回答其他问题。”

    Question: {question}
    =========
    Context: {context}
    =========
    """ + set_language

    template2 = """你是一个专业的宏观经济学习题解答助手！
在这里提供专业的宏观经济学题目解答服务。
问题描述： {question}
解答要求：
解析：请提供清晰、全面的解析，确保用词准确。
知识点总结：对涉及的宏观经济学知识点进行总结，并给出相关的学习建议。
专业限定： 请注意，我专注于宏观经济学领域的问题。对于非宏观经济学问题，将不提供解答。
参考例题：
在这里提供一个或多个与您的问题相关的参考例题。如果问题与参考例题相同，将提供与例题一致的答案，但需要进行答案解析的补充
{context}

输出格式，将遵循以下格式：
答案： 
解析： 
知识点总结（涉及的宏观经济学知识点总结）：
""" + set_language

    try:
        if(collection_name == "enocmics_book"):
            qa = llm_chain(collection_name,template1, vectorstore, 4, book_name)

            result = qa({"question": question, "chat_history": []})

            source = return_source(result, collection_name)

            emit("article_source", {'source': source})

        elif(collection_name == "economics_questions"):

            qa = llm_chain(collection_name, template2, vectorstore, 1, book_name)

            result = qa({"question": question, "chat_history": []})

            source = return_source(result, collection_name)


            emit("question_source", {'source': source})

    except Exception as e:

        print(e)



