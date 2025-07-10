

# do first on integrated terminal ===> conda activate ./condaEnvPython

from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough

import requests
from bs4 import BeautifulSoup

def fetch_web_content(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract the text content from the web page - find the text content from class
    text_content = soup.find("div", {'class': 'theme-doc-markdown markdown'}).get_text(separator=' ', )
    return text_content

def raw_content(url):
    response = requests.get(url)
    return BeautifulSoup(response.content, 'html.parser')

def preprocess_content(content):
    # Add any preprocessing steps here
    # For example, removing special characters, extra spaces, etc
    processed_content = content.replace('\n', ' ').strip()
    return processed_content

def get_stylusweb_introduction():
    url = 'https://docs.arbitrum.io/stylus/gentle-introduction'
    return preprocess_content(fetch_web_content(url))