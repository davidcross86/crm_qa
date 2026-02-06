import streamlit as st
from bs4 import BeautifulSoup
import requests
import re
from openai import OpenAI
import pandas as pd
import os
from urllib.parse import parse_qs, urlparse, unquote
import language_tool_python

# === OpenAI API Key (optional) ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    st.warning("OpenAI key not found. AI content review will be disabled.")

st.title("CRM Email QA Tool")

# === File uploader for HTML, MSG, EML ===
uploaded_file = st.file_uploader(
    "Upload an email file",
    type=["html", "msg", "eml"]
)

def unwrap_safelink(link):
    """If the link is an Outlook safelink, return the real URL."""
    if "safelinks.protection.outlook.com" in link:
        parsed = urlparse(link)
        qs = parse_qs(parsed.query)
        if "url" in qs:
            return unquote(qs["url"][0])
    return link

if uploaded_file:
    file_name = uploaded_file.name
    file_bytes = uploaded_file.read()
    html_content = ""
    subject_line = ""

    # === Process based on file type ===
    if file_name.endswith(".html"):
        html_content = file_bytes.decode("utf-8", errors="ignore")
        subject_line = "N/A"

    elif file_name.endswith(".msg"):
        import extract_msg
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

    # Ensure html_content is a string
    html_content = html_content or ""
    if isinstance(html_content, bytes):
        html_content = html_content.decode(errors="ignore")

    soup = BeautifulSoup(html_content, "html.parser")

    # === Subject line ===
    st.subheader("Subject Line")
    st.write(subject_line)

    # === Link extraction & checks ===
    links = [a['href'] for a in soup.find_all('a', href=True)]
    link_status = []

    for link in links:
        real_link = unwrap_safelink(link)
        status = "OK"
        try:
            r = requests.get(real_link, timeout=5)
            if r.status_code != 200:
                status = "Broken"
        except:
            status = "Broken"
        if "utm_" not in link:
            status += " (Missing UTM)"
        link_status.append({"Link": link, "Status": status})

    # === Display links table with color-coded status ===
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

    # === Personalization token check ===
    tokens = re.findall(r"\{\{.*?\}\}", html_content)
    st.subheader("Personalization Tokens")
    st.write(tokens or "None")

    # === Local Spell & Grammar Check ===
    st.subheader("Spell & Grammar Check (Local)")
    tool = language_tool_python.LanguageTool('en-US')
    email_text = soup.get_text()
    matches = tool.check(email_text or "")

    if matches:
        for match in matches:
            st.write(f"Issue: {match.message} | Suggestion: {', '.join(match.replacements) if match.replacements else 'No suggestion'}")
    else:
        st.write("No spelling or grammar issues found.")

    # === AI Content Review (optional) ===
    if OPENAI_API_KEY:
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
