import streamlit as st
from bs4 import BeautifulSoup
import requests
import re
from openai import OpenAI
import pandas as pd

# === OpenAI API Key from Streamlit secrets ===
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.error("OpenAI API key not found. Please add it to Streamlit secrets.")
    st.stop()

client = OpenAI(api_key=OPENAI_API_KEY)

st.title("CRM Email QA Tool")

# === File uploader ===
uploaded_file = st.file_uploader(
    "Upload an email file",
    type=["html", "msg", "eml"]
)

if uploaded_file:
    file_name = uploaded_file.name
    file_bytes = uploaded_file.read()

    html_content = ""
    subject_line = ""

    if file_name.endswith(".html"):
        html_content = file_bytes.decode("utf-8")
        subject_line = "N/A"

    elif file_name.endswith(".msg"):
        import extract_msg, os
        temp_path = f"/tmp/{file_name}"
        with open(temp_path, "wb") as f:
            f.write(file_bytes)
        msg = extract_msg.Message(temp_path)
        html_content = msg.body or msg.htmlBody or ""
        subject_line = msg.subject or "N/A"

    elif file_name.endswith(".eml"):
        import mailparser
        mail = mailparser.parse_from_bytes(file_bytes)
        html_content = mail.body_html or mail.body or ""
        subject_line = mail.subject or "N/A"

    if not html_content:
        st.warning("Could not extract content from this email.")
        st.stop()

    soup = BeautifulSoup(html_content, "html.parser")

    # === Subject line ===
    st.subheader("Subject Line")
    st.write(subject_line)

    # === Link check ===
    links = [a['href'] for a in soup.find_all('a', href=True)]
    link_status = []

    for link in links:
        status = "OK"
        try:
            r = requests.get(link, timeout=5)
            if r.status_code != 200:
                status = "Broken"
        except:
            status = "Broken"

        if "utm_" not in link:
            status += " (Missing UTM)"

        link_status.append({"Link": link, "Status": status})

    st.subheader("Links Table")
    df = pd.DataFrame(link_status)
    
    def color_status(val):
        if "Broken" in val:
            return "color: red"
        elif "Missing UTM" in val:
            return "color: orange"
        else:
            return "color: green"
    
    st.dataframe(df.style.applymap(color_status, subset=["Status"]))

    # === Personalization tokens ===
    tokens = re.findall(r"\{\{.*?\}\}", html_content)
    st.subheader("Personalization Tokens")
    st.write(tokens or "None")

    # === AI Content Review ===
    st.subheader("AI Content Review")
    email_text = soup.get_text()
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
