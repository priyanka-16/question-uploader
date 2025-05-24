from pymongo import MongoClient
import streamlit as st

def save_to_mongodb(questions):
    client = MongoClient(st.secrets['mongodb']['uri'])
    db = client["test"]
    collection = db["questions"]
    result = collection.insert_many(questions)
    return result.inserted_ids
