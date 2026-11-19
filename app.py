"""Small Streamlit dashboard for discovery, Gemini/Claude drafts, and Gmail approval."""

import streamlit as st

from config import settings
from services.claude_writer import generate_emails
from services.company_finder import discover_companies
from services.contact_finder import find_contacts
from services.gmail_service import create_draft, send_draft
from services.tracker import Tracker

st.set_page_config(page_title="Internship Hunter", layout="wide")
st.title("Personal Internship Hunter")
st.caption(f"AI provider: {settings.ai_provider}. Gmail sending always requires your explicit approval.")
st.info("This tool discovers companies first, then finds people at those companies for direct outreach. It does not submit job applications.")

for key, default in (("contacts", {}), ("drafts", {}), ("draft_ids", {})):
    if key not in st.session_state:
        st.session_state[key] = default

tracker = Tracker(settings.database_path)
try:
    count = st.sidebar.number_input("Companies to discover", min_value=1, max_value=30, value=5)
    if st.sidebar.button("Start discovery", type="primary"):
        with st.spinner("Searching..."):
            for company in discover_companies(int(count)):
                tracker.save_company(company)
        st.success("Discovery complete. Refresh the company list below if needed.")

    rows = tracker.list_companies()
    if not rows:
        st.info("Add SEARCH_API_KEY to .env, then click Start discovery.")

    for row in rows:
        company_key = str(row["id"])
        with st.expander(f"{row['match_score']}/100 - {row['name']}"):
            st.write(row["description"])
            st.markdown(f"[Opening/source]({row['source_url']})")
            st.write(f"Why it matches: {row['match_reason']}")

            if st.button("Find contacts", key=f"contacts-button-{company_key}"):
                try:
                    with st.spinner("Checking Hunter..."):
                        st.session_state.contacts[company_key] = find_contacts(row["website"])
                except Exception as error:
                    st.error(str(error))

            contacts = st.session_state.contacts.get(company_key, [])
            if contacts:
                for index, contact in enumerate(contacts):
                    contact_key = f"{company_key}-{index}"
                    st.write(f"**{contact.get('name') or 'Contact'}** — {contact['designation']} — `{contact['email']}`")
                    if st.button("Generate email options", key=f"generate-{contact_key}"):
                        try:
                            with st.spinner("Writing with AI..."):
                                st.session_state.drafts[contact_key] = generate_emails(dict(row), contact)
                        except Exception as error:
                            st.error(str(error))

                    drafts = st.session_state.drafts.get(contact_key)
                    if drafts:
                        for label, prefix in (("Professional", "professional"), ("Technical", "technical")):
                            st.subheader(label)
                            subject = st.text_input("Subject", drafts[f"{prefix}_subject"], key=f"subject-{contact_key}-{prefix}")
                            body = st.text_area("Body", drafts[f"{prefix}_body"], height=240, key=f"body-{contact_key}-{prefix}")
                            if st.button("Create Gmail draft", key=f"gmail-{contact_key}-{prefix}"):
                                try:
                                    draft_id = create_draft(contact["email"], subject, body, settings.resume_path)
                                    st.session_state.draft_ids[f"{contact_key}-{prefix}"] = draft_id
                                    st.success(f"Draft created: {draft_id}. Review it in Gmail before sending.")
                                except Exception as error:
                                    st.error(str(error))

                            draft_key = f"{contact_key}-{prefix}"
                            if draft_key in st.session_state.draft_ids:
                                st.warning("Review the draft in Gmail before sending.")
                                approved = st.checkbox("I reviewed and approve this email", key=f"approve-{draft_key}")
                                if approved and st.button("Send approved draft", key=f"send-{draft_key}"):
                                    try:
                                        sent_id = send_draft(st.session_state.draft_ids[draft_key])
                                        st.success(f"Sent. Gmail message ID: {sent_id}")
                                        del st.session_state.draft_ids[draft_key]
                                    except Exception as error:
                                        st.error(str(error))
            elif company_key in st.session_state.contacts:
                st.info("No suitable recruiting or founder contacts were found for this company.")
finally:
    tracker.close()
