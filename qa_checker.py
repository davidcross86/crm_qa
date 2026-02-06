import streamlit as st
from bs4 import BeautifulSoup
import requests
import re
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load .env only locally; Streamlit Cloud uses Secrets
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

st.title("CRM Email QA Tool")

# File uploader
uploaded_file = st.file_uploader("Upload an HTML email file", type=["html"])
if uploaded_file:
    html_content = uploaded_file.read().decode("utf-8")
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract links
    links = [a['href'] for a in soup.find_all('a', href=True)]
    broken_links = []
    missing_utms = []

    for link in links:
        try:
            r = requests.get(link, timeout=5)
            if r.status_code != 200:
                broken_links.append(link)
            if "utm_" not in link:
                missing_utms.append(link)
        except:
            broken_links.append(link)

    st.subheader("Broken Links")
    st.write(broken_links or "None")

    st.subheader("Links Missing UTM")
    st.write(missing_utms or "None")

    # Personalization tokens
    tokens = re.findall(r"\{\{.*?\}\}", html_content)
    st.subheader("Personalization Tokens")
    st.write(tokens or "None")

    # AI content review
    email_text = soup.get_text()
    st.subheader("AI Content Review")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an email QA assistant for financial services marketing."},
                {"role": "user", "content": f"Review this email content for grammar, tone, clarity and compliance risks:\n\n{email_text}"}
            ]
        )
        st.write(response.choices[0].message.content)
    except Exception as e:
        st.error(f"AI review failed: {e}")
