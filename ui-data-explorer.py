
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Dataset Explorer")


st.title('Dataset Explorer')

dataframe = pd.read_csv('./stylus-examples.csv')
st.dataframe(data=dataframe)

dataframeQA = pd.read_json('./data/q&a_arbitrum.jsonl', lines=True)
dataframeQA["Category"] = "General"
dataframeQAStylus = pd.read_json('./data/q&a_v4.jsonl', lines=True)
dataframeQAStylus["Category"] = "Stylus"
st.dataframe(data=pd.concat([dataframeQA, dataframeQAStylus]))