"""Small Streamlit dashboard for discovery, Claude drafts, and Gmail approval."""

import streamlit as st

from config import settings
from services.claude_writer import generate_emails
from services.company_finder import discover_companies
from services.contact_finder import find_contacts
from services.gmail_service import create_draft, send_draft
from services.tracker import Tracker

st.set_page_config(page_title="Internship Hunter", layout="wide")
st.title("Personal Internship Hunter")
st.caption(f"AI provider: {settings.ai_provider}. Discovery and draft preparation only. Gmail sending always requires your explicit click.")

tracker = Tracker(settings.database_path)
try:
    if "draft_ids" not in st.session_state:
        st.session_state.draft_ids = {}
    count = st.sidebar.number_input("Companies to discover", min_value=1, max_value=30, value=5)
    if st.sidebar.button("Start discovery", type="primary"):
        with st.spinner("Searching..."):
            for company in discover_companies(int(count)):
                tracker.save_company(company)
        st.success("Discovery complete.")

    rows = tracker.list_companies()
    if not rows:
        st.info("Add SEARCH_API_KEY to .env, then start discovery.")
    for row in rows:
        with st.expander(f"{row['match_score']}/100 - {row['name']}"):
            st.write(row["description"])
            st.markdown(f"[Opening/source]({row['source_url']})")
            st.write(f"Why it matches: {row['match_reason']}")
            if st.button("Find contacts", key=f"contacts-{row['id']}"):
                try:
                    contacts = find_contacts(row["website"])
                    if not contacts:
                        st.warning("No recruiting/founder contacts found.")
                    for contact in contacts:
                        st.json(contact)
                        if st.button(f"Draft for {contact['email']}", key=f"draft-{row['id']}-{contact['email']}"):
                            with st.spinner("Claude is writing..."):
                                drafts = generate_emails(dict(row), contact)
                            for label, prefix in (("Professional", "professional"), ("Technical", "technical")):
                                st.subheader(label)
                                subject = st.text_input("Subject", drafts[f"{prefix}_subject"], key=f"sub-{row['id']}-{prefix}")
                                body = st.text_area("Body", drafts[f"{prefix}_body"], height=260, key=f"body-{row['id']}-{prefix}")
                                if st.button("Create Gmail draft", key=f"gmail-{row['id']}-{prefix}"):
                                    draft_id = create_draft(contact["email"], subject, body, settings.resume_path)
                                    st.session_state.draft_ids[f"{row['id']}-{prefix}"] = draft_id
                                    st.success(f"Gmail draft created: {draft_id}. Review it in Gmail before sending.")
                                draft_key = f"{row['id']}-{prefix}"
                                if draft_key in st.session_state.draft_ids:
                                    st.warning("Only click send after reviewing the draft in Gmail.")
                                    approved = st.checkbox("I reviewed and approve this email", key=f"approve-{draft_key}")
                                    if approved and st.button("Send approved draft", key=f"send-{draft_key}"):
                                        sent_id = send_draft(st.session_state.draft_ids[draft_key])
                                        st.success(f"Sent. Gmail message ID: {sent_id}")
                                        del st.session_state.draft_ids[draft_key]
                except Exception as error:
                    st.error(str(error))
finally:
    tracker.close()
