import html
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable

from dotenv import load_dotenv
from bson import ObjectId
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError


def log(message: str) -> None:
    print(f"[lab1-worker] {message}", flush=True)


def parse_interval(raw_value: str) -> int:
    # keep polling sane even with missing/bad env values
    try:
        interval = int(raw_value)
        return interval if interval > 0 else 5
    except (TypeError, ValueError):
        return 5


def get_database(client: MongoClient):
    # if the URI already points to a db, use it; otherwise fallback to mzinga
    db = client.get_default_database()
    if db is not None:
        return db
    return client["mzinga"]


def extract_object_id(value):
    # relationship values can arrive as raw ids or nested payload objects
    if value is None:
        return None
    if isinstance(value, dict):
        if value.get("id"):
            value = value.get("id")
        elif value.get("_id"):
            value = value.get("_id")
        else:
            return None
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str):
        return value
    try:
        as_text = str(value)
        if ObjectId.is_valid(as_text):
            return ObjectId(as_text)
    except Exception:
        return None
    return value


def resolve_emails(user_collection, relationships: Iterable) -> list[str]:
    # convert relationship refs (tos/ccs/bccs) into email strings from users
    if not relationships:
        return []

    user_ids = []
    for entry in relationships:
        if not isinstance(entry, dict):
            continue
        user_id = extract_object_id(entry.get("value"))
        if user_id:
            user_ids.append(user_id)

    if not user_ids:
        return []

    users_cursor = user_collection.find({"_id": {"$in": user_ids}}, {"email": 1})
    users_by_id = {str(user["_id"]): user.get("email") for user in users_cursor}

    emails = []
    for user_id in user_ids:
        email = users_by_id.get(str(user_id))
        if email:
            emails.append(email)
    return emails


def serialize_nodes(nodes) -> str:
    # body is stored as Slate AST; render it to html for smtp
    if not isinstance(nodes, list):
        return ""
    rendered = [serialize_node(node) for node in nodes]
    return "".join(part for part in rendered if part)


def serialize_node(node) -> str:
    if not isinstance(node, dict):
        return ""

    if "text" in node:
        # escape text first, then apply inline marks
        text = html.escape(str(node.get("text", ""))).replace("\n", "<br/>")
        if not text:
            return ""
        text = f"<span>{text}</span>"
        if node.get("bold"):
            text = f"<strong>{text}</strong>"
        if node.get("italic"):
            text = f"<em>{text}</em>"
        return text

    node_type = node.get("type")
    children_html = serialize_nodes(node.get("children", []))

    if node_type == "paragraph":
        return f"<p>{children_html}</p>"
    if node_type == "h1":
        return f"<h1>{children_html}</h1>"
    if node_type == "h2":
        return f"<h2>{children_html}</h2>"
    if node_type == "ul":
        return f"<ul>{children_html}</ul>"
    if node_type == "li":
        return f"<li>{children_html}</li>"
    if node_type == "link":
        # support both external links and payload internal links
        if node.get("linkType") == "internal":
            doc_id = (
                node.get("doc", {})
                .get("value", {})
                .get("id")
            )
            href = f"#{doc_id}" if doc_id else "#"
        else:
            href = node.get("url") or "#"
        attrs = f' href="{html.escape(str(href), quote=True)}"'
        if node.get("newTab"):
            attrs += ' target="_blank" rel="noopener noreferrer"'
        return f"<a{attrs}>{children_html}</a>"

    if node_type:
        return f"<p>{children_html}</p>"
    return children_html


def send_email(
    smtp_host: str,
    smtp_port: int,
    from_email: str,
    subject: str,
    to_emails: list[str],
    cc_emails: list[str],
    bcc_emails: list[str],
    html_body: str,
) -> None:
    # send a single html email via local smtp sink (mailhog in lab setup)
    message = MIMEMultipart("alternative")
    message["From"] = from_email
    message["To"] = ", ".join(to_emails)
    message["Subject"] = subject

    if cc_emails:
        message["Cc"] = ", ".join(cc_emails)

    message.attach(MIMEText(html_body, "html", "utf-8"))
    recipients = to_emails + cc_emails + bcc_emails

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
        smtp.sendmail(from_email, recipients, message.as_string())


def process_communication(doc, communication_collection, users_collection, config) -> None:
    # process one claimed communication and move it to sent on success
    doc_id = doc["_id"]
    subject = str(doc.get("subject") or "")
    body_html = serialize_nodes(doc.get("body") or [])

    tos = resolve_emails(users_collection, doc.get("tos"))
    ccs = resolve_emails(users_collection, doc.get("ccs"))
    bccs = resolve_emails(users_collection, doc.get("bccs"))

    if not tos:
        raise ValueError("No valid recipient addresses resolved from 'tos'.")

    send_email(
        smtp_host=config["smtp_host"],
        smtp_port=config["smtp_port"],
        from_email=config["email_from"],
        subject=subject,
        to_emails=tos,
        cc_emails=ccs,
        bcc_emails=bccs,
        html_body=body_html,
    )

    communication_collection.update_one(
        {"_id": doc_id},
        {"$set": {"status": "sent"}},
    )
    log(f"{doc_id} sent")


def main() -> None:
    load_dotenv()

    mongodb_uri = os.getenv("MONGODB_URI", "").strip()
    poll_interval = parse_interval(os.getenv("POLL_INTERVAL_SECONDS", "5"))
    smtp_host = os.getenv("SMTP_HOST", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "1025"))
    email_from = os.getenv("EMAIL_FROM", "worker@mzinga.io")

    if not mongodb_uri:
        raise RuntimeError("MONGODB_URI is required.")

    config = {
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "email_from": email_from,
    }

    client = MongoClient(mongodb_uri)
    db = get_database(client)
    communication_collection = db["communications"]
    users_collection = db["users"]

    log("worker started")
    log(f"poll interval: {poll_interval}s")
    log(f"smtp target: {smtp_host}:{smtp_port}")

    while True:
        try:
            # atomic claim: only one worker can move pending -> processing
            claimed_doc = communication_collection.find_one_and_update(
                {"status": "pending"},
                {"$set": {"status": "processing"}},
                sort=[("createdAt", 1)],
                return_document=ReturnDocument.AFTER,
            )

            if claimed_doc is None:
                time.sleep(poll_interval)
                continue

            doc_id = claimed_doc["_id"]
            log(f"{doc_id} claimed")

            try:
                process_communication(
                    claimed_doc,
                    communication_collection,
                    users_collection,
                    config,
                )
            except Exception as err:
                # keep failed docs visible for manual retry (set back to pending)
                communication_collection.update_one(
                    {"_id": doc_id},
                    {"$set": {"status": "failed"}},
                )
                log(f"{doc_id} failed: {err}")
        except PyMongoError as err:
            log(f"mongodb error: {err}")
            time.sleep(poll_interval)
        except Exception as err:
            log(f"unexpected error: {err}")
            time.sleep(poll_interval)


if __name__ == "__main__":
    main()
