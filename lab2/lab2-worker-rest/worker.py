import html
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable

import requests
from dotenv import load_dotenv


def log(message: str) -> None:
    print(f"[lab2-worker-rest] {message}", flush=True)


def parse_int(raw_value: str, fallback: int) -> int:
    # keep numeric env parsing stable even when missing or malformed
    try:
        parsed = int(raw_value)
        return parsed if parsed > 0 else fallback
    except (TypeError, ValueError):
        return fallback


def normalize_base_url(base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    return normalized or "http://localhost:3000"


def require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


def serialize_nodes(nodes) -> str:
    # body is stored as Slate AST; render to html used by smtp
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
            doc_id = node.get("doc", {}).get("value", {}).get("id")
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


def extract_emails(relationships: Iterable) -> list[str]:
    # depth=1 gives resolved users under entry.value.email
    if not relationships:
        return []

    emails: list[str] = []
    for entry in relationships:
        email = None
        if isinstance(entry, dict):
            value = entry.get("value")
            if isinstance(value, dict):
                email = value.get("email")
            elif isinstance(entry.get("email"), str):
                email = entry.get("email")

        if isinstance(email, str):
            email = email.strip()
            if email and email not in emails:
                emails.append(email)

    return emails


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
    # send a single html email through local smtp sink (mailhog in lab setup)
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


class MzingaApiClient:
    def __init__(self, base_url: str, email: str, password: str, timeout_seconds: int = 20):
        self.base_url = normalize_base_url(base_url)
        self.email = email
        self.password = password
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.token: str | None = None

    def authenticate(self) -> None:
        response = self.session.post(
            f"{self.base_url}/api/users/login",
            json={
                "email": self.email,
                "password": self.password,
            },
            timeout=self.timeout_seconds,
        )
        self.raise_for_status(response, "login")
        response_payload = response.json()
        token = response_payload.get("token")
        if not token:
            raise RuntimeError("login response did not include token")
        self.token = token
        log("authenticated to mzinga api")

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        retry_on_unauthorized: bool = True,
    ) -> requests.Response:
        if not self.token:
            self.authenticate()

        response = self.session.request(
            method=method.upper(),
            url=f"{self.base_url}{path}",
            params=params,
            json=json_body,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=self.timeout_seconds,
        )

        if response.status_code == 401 and retry_on_unauthorized:
            # refresh jwt and retry once when token expires
            log("received 401, re-authenticating")
            self.authenticate()
            return self.request(
                method=method,
                path=path,
                params=params,
                json_body=json_body,
                retry_on_unauthorized=False,
            )

        return response

    def get_pending_communications(self) -> list[dict]:
        response = self.request(
            "GET",
            "/api/communications",
            params={
                "where[status][equals]": "pending",
                "depth": 1,
                "limit": 50,
                "sort": "createdAt",
            },
        )
        self.raise_for_status(response, "list pending communications")
        payload = response.json()
        docs = payload.get("docs")
        if isinstance(docs, list):
            return docs
        return []

    def get_communication(self, communication_id: str) -> dict | None:
        response = self.request(
            "GET",
            f"/api/communications/{communication_id}",
            params={"depth": 1},
        )
        if response.status_code == 404:
            return None
        self.raise_for_status(response, f"fetch communication {communication_id}")
        return response.json()

    def set_status(self, communication_id: str, status: str) -> None:
        response = self.request(
            "PATCH",
            f"/api/communications/{communication_id}",
            json_body={"status": status},
        )
        self.raise_for_status(response, f"patch status={status} for {communication_id}")

    @staticmethod
    def raise_for_status(response: requests.Response, action: str) -> None:
        if response.ok:
            return
        response_body = (response.text or "").strip().replace("\n", " ")
        if len(response_body) > 300:
            response_body = response_body[:300] + "..."
        raise RuntimeError(
            f"{action} failed with {response.status_code}: {response_body}"
        )


def process_communication(document: dict, config: dict) -> None:
    # serialize body and deliver through smtp
    subject = str(document.get("subject") or "")
    body_html = serialize_nodes(document.get("body") or [])

    tos = extract_emails(document.get("tos"))
    ccs = extract_emails(document.get("ccs"))
    bccs = extract_emails(document.get("bccs"))

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


def main() -> None:
    load_dotenv()

    config = {
        "api_base_url": os.getenv("MZINGA_API_BASE_URL", "http://localhost:3000"),
        "admin_email": require_env("MZINGA_ADMIN_EMAIL"),
        "admin_password": require_env("MZINGA_ADMIN_PASSWORD"),
        "poll_interval_seconds": parse_int(os.getenv("POLL_INTERVAL_SECONDS", "5"), 5),
        "smtp_host": os.getenv("SMTP_HOST", "localhost"),
        "smtp_port": parse_int(os.getenv("SMTP_PORT", "1025"), 1025),
        "email_from": os.getenv("EMAIL_FROM", "worker@mzinga.io"),
    }

    api_client = MzingaApiClient(
        base_url=config["api_base_url"],
        email=config["admin_email"],
        password=config["admin_password"],
    )
    api_client.authenticate()

    log("worker started")
    log(
        "settings: "
        f"api={normalize_base_url(config['api_base_url'])}, "
        f"poll={config['poll_interval_seconds']}s"
    )

    while True:
        try:
            pending_docs = api_client.get_pending_communications()

            if not pending_docs:
                time.sleep(config["poll_interval_seconds"])
                continue

            for pending_doc in pending_docs:
                communication_id = str(pending_doc.get("id") or "").strip()
                if not communication_id:
                    continue

                try:
                    api_client.set_status(communication_id, "processing")
                    log(f"{communication_id} set to processing")

                    full_document = api_client.get_communication(communication_id)
                    if not full_document:
                        log(f"{communication_id} not found after claim")
                        continue

                    process_communication(full_document, config)
                    api_client.set_status(communication_id, "sent")
                    log(f"{communication_id} sent")
                except Exception as err:
                    try:
                        api_client.set_status(communication_id, "failed")
                    except Exception as patch_err:
                        log(f"{communication_id} failed and status patch failed: {patch_err}")
                    log(f"{communication_id} failed: {err}")

            time.sleep(config["poll_interval_seconds"])
        except Exception as err:
            log(f"loop error: {err}")
            time.sleep(config["poll_interval_seconds"])


if __name__ == "__main__":
    main()
