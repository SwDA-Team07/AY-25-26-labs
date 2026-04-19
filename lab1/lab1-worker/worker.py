import os
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", 5))
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
EMAIL_FROM = os.getenv("EMAIL_FROM")

# STEP 1: Connect to MongoDB using pymongo and the MONGODB_URI from the environment
client = MongoClient(MONGODB_URI)
db = client["mzinga"]
communications_col = db["communications"]
users_col = db["users"]


def serialize_slate_to_html(nodes):
    """
    STEP 5: Serialise the body to HTML.
    Recursively convert Slate AST nodes to HTML.
    Handles: paragraph, h1, h2, ul, li, link, and leaf text nodes with bold/italic marks.
    """
    if not nodes:
        return ""
    
    html = ""
    for node in nodes:
        if not isinstance(node, dict):
            # Text leaf node
            text = str(node)
            if isinstance(nodes, dict) and "bold" in nodes.get("__marks", []):
                text = f"<strong>{text}</strong>"
            if isinstance(nodes, dict) and "italic" in nodes.get("__marks", []):
                text = f"<em>{text}</em>"
            html += text
            continue
        
        node_type = node.get("type")
        children = node.get("children", [])
        
        if node_type == "paragraph":
            html += "<p>" + serialize_slate_to_html(children) + "</p>"
        elif node_type == "h1":
            html += "<h1>" + serialize_slate_to_html(children) + "</h1>"
        elif node_type == "h2":
            html += "<h2>" + serialize_slate_to_html(children) + "</h2>"
        elif node_type == "ul":
            html += "<ul>" + serialize_slate_to_html(children) + "</ul>"
        elif node_type == "li":
            html += "<li>" + serialize_slate_to_html(children) + "</li>"
        elif node_type == "link":
            url = node.get("url", "#")
            html += f'<a href="{url}">' + serialize_slate_to_html(children) + "</a>"
        elif node_type == "text":
            text = node.get("text", "")
            marks = node.get("marks", [])
            if "bold" in marks:
                text = f"<strong>{text}</strong>"
            if "italic" in marks:
                text = f"<em>{text}</em>"
            html += text
        else:
            # Default: recursively process children
            html += serialize_slate_to_html(children)
    
    return html


def resolve_emails(relationships):
    """
    STEP 4: Resolve recipient email addresses.
    Convert relationship references to actual email addresses.
    Relationships are in the form: [{ "relationTo": "users", "value": <ObjectId> }]
    """
    if not relationships:
        return []
    
    emails = []
    for rel in relationships:
        user_id = rel.get("value")
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        user = users_col.find_one({"_id": user_id})
        if user and "email" in user:
            emails.append(user["email"])
    
    return emails


def send_email(to_addresses, cc_addresses, bcc_addresses, subject, html_body):
    """
    STEP 6: Send the email using Python's built-in smtplib.
    Build a MIMEMultipart message and send it via the configured SMTP host and port.
    """
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = ", ".join(to_addresses)
        if cc_addresses:
            msg["Cc"] = ", ".join(cc_addresses)
        
        msg.attach(MIMEText(html_body, "html"))
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.sendmail(
                EMAIL_FROM,
                to_addresses + cc_addresses + bcc_addresses,
                msg.as_string()
            )
        
        print(f"✓ Email sent to {to_addresses}")
        return True
    except Exception as e:
        print(f"✗ Failed to send email: {e}")
        return False


def process_communication(doc):
    """Communication document that is already marked as 'processing'.
    """
    doc_id = doc["_id"]
    
    try:
        # STEP 4: Resolve recipient email addresses
        to_emails = resolve_emails(doc.get("tos", []))
        cc_emails = resolve_emails(doc.get("ccs", []))
        bcc_emails = resolve_emails(doc.get("bccs", []))
        
        if not to_emails:
            raise Exception("No 'to' recipients found")
        
        # STEP 5: Serialise the body to HTML
        body_html = serialize_slate_to_html(doc.get("body", []))
        
        # STEP 6: Send the email
        subject = doc.get("subject", "")
        success = send_email(to_emails, cc_emails, bcc_emails, subject, body_html)
        
        # STEP 7: Write back the result
        if success:
            communications_col.update_one(
                {"_id": doc_id},
                {"$set": {"status": "sent"}}
            )
            print(f"✓ Document {doc_id} marked as 'sent'")
        else:
            communications_col.update_one(
                {"_id": doc_id},
                {"$set": {"status": "failed"}}
            )
            print(f"✗ Document {doc_id} marked as 'failed'")
    
    except Exception as e:
        print(f"✗ Error processing document {doc_id}: {e}")
        # STEP 7: Write back the result (failure case
        print(f"✗ Error processing document {doc_id}: {e}")
        communications_col.update_one(
            {"_id": doc_id},
            {"$set": {"status": "failed"}}
        )


def main():
    """
    Main worker loop: poll for pending communications and process them.
    """
    print(f"Worker started. Polling every {POLL_INTERVAL_SECONDS} seconds...")
    
    while True:
        try:
            # STEP 2: Poll for pending documents
            # STEP 3: Claim the document by immediately updating its status to "processing"
            doc = communications_col.find_one_and_update(
                {"status": "pending"},
                {"$set": {"status": "processing"}},
                return_document=True
            )
            
            if doc:
                print(f"\n📧 Processing document {doc['_id']}...")
                process_communication(doc)
            else:
                # No pending documents, sleep
                time.sleep(POLL_INTERVAL_SECONDS)
        
        except Exception as e:
            print(f"✗ Worker error: {e}")
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
