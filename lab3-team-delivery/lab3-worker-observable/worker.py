import html
import logging
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable

import requests
import structlog
from dotenv import load_dotenv

# OpenTelemetry Imports
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# 1. Configurazione OpenTelemetry (Tracing)
SERVICE_NAME = "email-worker"
resource = Resource.create({
    "service.name": SERVICE_NAME,
    "service.version": "1.0.0"
})

otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(exporter)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

RequestsInstrumentor().instrument()
tracer = trace.get_tracer(SERVICE_NAME)

def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            # Inietta automaticamente trace_id e span_id nei log se presenti
            add_tracing_context, 
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )

def add_tracing_context(_, __, event_dict):
    """Processor per structlog che aggiunge trace info ai log JSON"""
    span_context = trace.get_current_span().get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, '032x')
        event_dict["span_id"] = format(span_context.span_id, '016x')
    return event_dict

log = structlog.get_logger(service=SERVICE_NAME)

# --- Helper Functions ---

def parse_int(raw_value: str, fallback: int) -> int:
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

# --- Core Logic with Tracing ---

def serialize_nodes(nodes: list) -> str:
    """Requirement 3.3: Manual span for serialization"""
    with tracer.start_as_current_span("serialize_body") as span:
        count = len(nodes) if isinstance(nodes, list) else 0
        span.set_attribute("node_count", count)
        
        if not isinstance(nodes, list):
            return ""
        rendered = [serialize_node(node) for node in nodes]
        return "".join(part for part in rendered if part)

def serialize_node(node) -> str:
    if not isinstance(node, dict):
        return ""
    if "text" in node:
        text = html.escape(str(node.get("text", ""))).replace("\n", "<br/>")
        if not text: return ""
        text = f"<span>{text}</span>"
        if node.get("bold"): text = f"<strong>{text}</strong>"
        if node.get("italic"): text = f"<em>{text}</em>"
        return text

    node_type = node.get("type")
    children_html = serialize_nodes(node.get("children", []))
    tags = {"paragraph": "p", "h1": "h1", "h2": "h2", "ul": "ul", "li": "li"}
    
    if node_type in tags:
        tag = tags[node_type]
        return f"<{tag}>{children_html}</{tag}>"
    
    if node_type == "link":
        if node.get("linkType") == "internal":
            doc_id = node.get("doc", {}).get("value", {}).get("id")
            href = f"#{doc_id}" if doc_id else "#"
        else:
            href = node.get("url") or "#"
        attrs = f' href="{html.escape(str(href), quote=True)}"'
        if node.get("newTab"):
            attrs += ' target="_blank" rel="noopener noreferrer"'
        return f"<a{attrs}>{children_html}</a>"

    return children_html

def extract_emails(relationships: Iterable) -> list[str]:
    if not relationships: return []
    emails: list[str] = []
    for entry in relationships:
        email = None
        if isinstance(entry, dict):
            value = entry.get("value")
            email = value.get("email") if isinstance(value, dict) else entry.get("email")
        if isinstance(email, str):
            email = email.strip()
            if email and email not in emails: emails.append(email)
    return emails

def send_email(smtp_host, smtp_port, from_email, subject, to_emails, cc_emails, bcc_emails, html_body):
    """Requirement 3.3: Manual span for SMTP"""
    with tracer.start_as_current_span("send_email") as span:
        all_recipients = to_emails + cc_emails + bcc_emails
        span.set_attribute("recipient_count", len(all_recipients))
        try:
            message = MIMEMultipart("alternative")
            message["From"] = from_email
            message["To"] = ", ".join(to_emails)
            message["Subject"] = subject
            if cc_emails: message["Cc"] = ", ".join(cc_emails)
            message.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
                smtp.sendmail(from_email, all_recipients, message.as_string())
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            span.record_exception(e)
            raise e

class MzingaApiClient:
    def __init__(self, base_url, email, password):
        self.base_url = normalize_base_url(base_url)
        self.email = email
        self.password = password
        self.session = requests.Session()
        self.token = None

    def authenticate(self):
        resp = self.session.post(f"{self.base_url}/api/users/login", 
                                 json={"email": self.email, "password": self.password}, timeout=20)
        self.raise_for_status(resp, "login")
        self.token = resp.json().get("token")
        log.info("authenticated")

    def request(self, method, path, **kwargs):
        if not self.token: self.authenticate()
        kwargs.setdefault("headers", {})["Authorization"] = f"Bearer {self.token}"
        resp = self.session.request(method, f"{self.base_url}{path}", timeout=20, **kwargs)
        if resp.status_code == 401:
            self.authenticate()
            return self.request(method, path, **kwargs)
        return resp

    def get_pending_communications(self):
        resp = self.request("GET", "/api/communications", 
                            params={"where[status][equals]": "pending", "depth": 1, "limit": 50})
        return resp.json().get("docs", [])

    def get_communication(self, comm_id):
        resp = self.request("GET", f"/api/communications/{comm_id}", params={"depth": 1})
        return resp.json() if resp.ok else None

    def set_status(self, comm_id, status):
        self.request("PATCH", f"/api/communications/{comm_id}", json={"status": status})

    @staticmethod
    def raise_for_status(resp, action):
        if not resp.ok: raise RuntimeError(f"{action} failed: {resp.status_code}")

def process_communication(document: dict, config: dict) -> None:
    """Requirement 3.3: Root span for processing"""
    with tracer.start_as_current_span("process_communication") as span:
        doc_id = str(document.get("id"))
        span.set_attribute("doc_id", doc_id)
        log.info("starting_processing")
        
        try:
            subject = str(document.get("subject") or "")
            body_html = serialize_nodes(document.get("body") or [])
            tos = extract_emails(document.get("tos"))
            if not tos: raise ValueError("No recipients found")

            send_email(config["smtp_host"], config["smtp_port"], config["email_from"],
                       subject, tos, extract_emails(document.get("ccs")), 
                       extract_emails(document.get("bccs")), body_html)
            
            log.info("email_delivery_completed")
        except Exception as e:
            span.set_status(trace.Status(trace.StatusCode.ERROR))
            span.record_exception(e)
            log.error("processing_failed", error=str(e))
            raise e

def main():
    load_dotenv()
    configure_logging()

    config = {
        "api_base_url": os.getenv("MZINGA_API_BASE_URL", "http://localhost:3000"),
        "admin_email": require_env("MZINGA_ADMIN_EMAIL"),
        "admin_password": require_env("MZINGA_ADMIN_PASSWORD"),
        "poll_interval": parse_int(os.getenv("POLL_INTERVAL_SECONDS", "5"), 5),
        "smtp_host": os.getenv("SMTP_HOST", "localhost"),
        "smtp_port": parse_int(os.getenv("SMTP_PORT", "1025"), 1025),
        "email_from": os.getenv("EMAIL_FROM", "worker@mzinga.io"),
    }

    api = MzingaApiClient(config["api_base_url"], config["admin_email"], config["admin_password"])
    log.info("worker_started", poll_interval=config["poll_interval"])

    while True:
        try:
            for doc in api.get_pending_communications():
                comm_id = doc.get("id")
                structlog.contextvars.bind_contextvars(doc_id=comm_id)
                try:
                    api.set_status(comm_id, "processing")
                    full_doc = api.get_communication(comm_id)
                    if full_doc:
                        process_communication(full_doc, config)
                        api.set_status(comm_id, "sent")
                        log.info("communication_sent")
                except Exception as e:
                    api.set_status(comm_id, "failed")
                    log.error("document_error", error=str(e))
                finally:
                    structlog.contextvars.unbind_contextvars("doc_id")
            time.sleep(config["poll_interval"])
        except Exception as e:
            log.error("loop_error", error=str(e))
            time.sleep(config["poll_interval"])

if __name__ == "__main__":
    main()