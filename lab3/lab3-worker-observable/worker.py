import html
import logging
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Iterable, List, Optional

import requests
import structlog
from dotenv import load_dotenv

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode
from prometheus_client import start_http_server


def parse_int(raw_value: Optional[str], fallback: int) -> int:
    try:
        parsed = int(str(raw_value))
        return parsed if parsed > 0 else fallback
    except (TypeError, ValueError):
        return fallback


def normalize_base_url(base_url: str) -> str:
    normalized = (base_url or "").strip().rstrip("/")
    return normalized or "http://localhost:3000"


def normalize_otlp_traces_endpoint(raw_endpoint: str) -> str:
    base = (raw_endpoint or "").strip().rstrip("/")
    if not base:
        base = "http://localhost:4318"
    if base.endswith("/v1/traces"):
        return base
    return f"{base}/v1/traces"


def require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required.")
    return value


def add_otel_context(_, __, event_dict: Dict) -> Dict:
    span = trace.get_current_span()
    span_context = span.get_span_context()
    if span_context.is_valid:
        event_dict["trace_id"] = format(span_context.trace_id, "032x")
        event_dict["span_id"] = format(span_context.span_id, "016x")
    return event_dict


def configure_logging(service_name: str):
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            add_otel_context,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
    return structlog.get_logger(service=service_name)


def build_config() -> Dict[str, object]:
    load_dotenv()

    return {
        "api_base_url": os.getenv("MZINGA_API_BASE_URL", "http://localhost:3000"),
        "admin_email": require_env("MZINGA_ADMIN_EMAIL"),
        "admin_password": require_env("MZINGA_ADMIN_PASSWORD"),
        "poll_interval_seconds": parse_int(os.getenv("POLL_INTERVAL_SECONDS", "5"), 5),
        "smtp_host": os.getenv("SMTP_HOST", "localhost"),
        "smtp_port": parse_int(os.getenv("SMTP_PORT", "1025"), 1025),
        "email_from": os.getenv("EMAIL_FROM", "worker@mzinga.io"),
        "otel_service_name": os.getenv("OTEL_SERVICE_NAME", "email-worker"),
        "otlp_endpoint": os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
        "prometheus_port": parse_int(os.getenv("PROMETHEUS_PORT", "8000"), 8000),
    }


def setup_observability(config: Dict[str, object], logger) -> Dict[str, object]:
    service_name = str(config["otel_service_name"])
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "1.0.0",
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter(
        endpoint=normalize_otlp_traces_endpoint(str(config["otlp_endpoint"])),
    )
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    try:
        RequestsInstrumentor().instrument()
    except Exception as err:
        logger.warning("requests_instrumentation_warning", error=str(err))

    prometheus_port = int(config["prometheus_port"])
    try:
        start_http_server(prometheus_port)
    except OSError as err:
        logger.warning(
            "prometheus_http_server_warning",
            prometheus_port=prometheus_port,
            error=str(err),
        )

    os.environ["OTEL_EXPORTER_PROMETHEUS_PORT"] = str(config["prometheus_port"])
    metric_reader = PrometheusMetricReader()
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    meter = metrics.get_meter(service_name)

    telemetry = {
        "tracer": trace.get_tracer(service_name),
        "emails_processed_total": meter.create_counter(
            name="emails_processed_total",
            description="Total number of communications processed",
            unit="1",
        ),
        "email_processing_duration_seconds": meter.create_histogram(
            name="email_processing_duration_seconds",
            description="End-to-end duration of one communication processing",
            unit="s",
        ),
        "smtp_send_duration_seconds": meter.create_histogram(
            name="smtp_send_duration_seconds",
            description="Duration of the SMTP send operation",
            unit="s",
        ),
        "worker_poll_total": meter.create_counter(
            name="worker_poll_total",
            description="Number of poll cycles",
            unit="1",
        ),
    }

    logger.info(
        "observability_initialized",
        otlp_traces_endpoint=normalize_otlp_traces_endpoint(str(config["otlp_endpoint"])),
        prometheus_port=int(config["prometheus_port"]),
    )

    return telemetry


def serialize_nodes(nodes) -> str:
    if not isinstance(nodes, list):
        return ""
    rendered = [serialize_node(node) for node in nodes]
    return "".join(part for part in rendered if part)


def serialize_node(node) -> str:
    if not isinstance(node, dict):
        return ""

    if "text" in node:
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


def extract_emails(relationships: Iterable) -> List[str]:
    if not relationships:
        return []

    emails: List[str] = []
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
    tracer,
    smtp_duration_hist,
    smtp_host: str,
    smtp_port: int,
    from_email: str,
    subject: str,
    to_emails: List[str],
    cc_emails: List[str],
    bcc_emails: List[str],
    html_body: str,
) -> None:
    with tracer.start_as_current_span("send_email") as span:
        span.set_attribute("recipient_count", len(to_emails) + len(cc_emails) + len(bcc_emails))

        started_at = time.perf_counter()
        message = MIMEMultipart("alternative")
        message["From"] = from_email
        message["To"] = ", ".join(to_emails)
        message["Subject"] = subject

        if cc_emails:
            message["Cc"] = ", ".join(cc_emails)

        message.attach(MIMEText(html_body, "html", "utf-8"))
        recipients = to_emails + cc_emails + bcc_emails

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
                smtp.sendmail(from_email, recipients, message.as_string())
        except Exception as err:
            span.set_status(Status(StatusCode.ERROR, str(err)))
            span.record_exception(err)
            raise
        finally:
            smtp_duration_hist.record(time.perf_counter() - started_at)


class MzingaApiClient:
    def __init__(self, base_url: str, email: str, password: str, timeout_seconds: int = 20):
        self.base_url = normalize_base_url(base_url)
        self.email = email
        self.password = password
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.token = None

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
        payload = response.json()
        token = payload.get("token")
        if not token:
            raise RuntimeError("login response did not include token")
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_body: Optional[dict] = None,
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
            self.authenticate()
            return self.request(
                method=method,
                path=path,
                params=params,
                json_body=json_body,
                retry_on_unauthorized=False,
            )

        return response

    def get_pending_communications(self) -> List[dict]:
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

    def get_communication(self, communication_id: str) -> Optional[dict]:
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
        raise RuntimeError(f"{action} failed with {response.status_code}: {response_body}")


def process_communication(
    document: dict,
    api_client: MzingaApiClient,
    config: Dict[str, object],
    telemetry: Dict[str, object],
    logger,
) -> None:
    tracer = telemetry["tracer"]
    emails_processed_total = telemetry["emails_processed_total"]
    processing_duration_hist = telemetry["email_processing_duration_seconds"]
    smtp_duration_hist = telemetry["smtp_send_duration_seconds"]

    communication_id = str(document.get("id") or "").strip()
    if not communication_id:
        logger.warning("missing_communication_id")
        return

    structlog.contextvars.bind_contextvars(doc_id=communication_id)
    started_at = time.perf_counter()

    with tracer.start_as_current_span("process_communication") as root_span:
        root_span.set_attribute("doc_id", communication_id)

        try:
            api_client.set_status(communication_id, "processing")
            logger.info("status_updated", status="processing")

            full_document = api_client.get_communication(communication_id)
            if not full_document:
                logger.warning("communication_not_found")
                return

            subject = str(full_document.get("subject") or "")

            with tracer.start_as_current_span("serialize_body") as serialize_span:
                body_nodes = full_document.get("body") or []
                node_count = len(body_nodes) if isinstance(body_nodes, list) else 0
                serialize_span.set_attribute("node_count", node_count)
                body_html = serialize_nodes(body_nodes)

            tos = extract_emails(full_document.get("tos"))
            ccs = extract_emails(full_document.get("ccs"))
            bccs = extract_emails(full_document.get("bccs"))

            if not tos:
                raise ValueError("No valid recipient addresses resolved from 'tos'.")

            send_email(
                tracer=tracer,
                smtp_duration_hist=smtp_duration_hist,
                smtp_host=str(config["smtp_host"]),
                smtp_port=int(config["smtp_port"]),
                from_email=str(config["email_from"]),
                subject=subject,
                to_emails=tos,
                cc_emails=ccs,
                bcc_emails=bccs,
                html_body=body_html,
            )

            api_client.set_status(communication_id, "sent")
            logger.info("status_updated", status="sent")

            duration_seconds = time.perf_counter() - started_at
            processing_duration_hist.record(duration_seconds)
            emails_processed_total.add(
                1,
                {
                    "status": "sent",
                    "recipient_count": len(tos),
                },
            )
            logger.info(
                "processing_completed",
                status="sent",
                recipient_count=len(tos),
                duration_s=round(duration_seconds, 3),
            )
        except Exception as err:
            root_span.set_status(Status(StatusCode.ERROR, str(err)))
            root_span.record_exception(err)

            try:
                api_client.set_status(communication_id, "failed")
                logger.info("status_updated", status="failed")
            except Exception as patch_err:
                logger.error("status_update_failed", error=str(patch_err))

            duration_seconds = time.perf_counter() - started_at
            processing_duration_hist.record(duration_seconds)
            emails_processed_total.add(
                1,
                {
                    "status": "failed",
                    "recipient_count": 0,
                },
            )
            logger.error(
                "processing_failed",
                status="failed",
                error=str(err),
                duration_s=round(duration_seconds, 3),
            )
        finally:
            structlog.contextvars.unbind_contextvars("doc_id")


def main() -> None:
    config = build_config()
    logger = configure_logging(str(config["otel_service_name"]))
    telemetry = setup_observability(config, logger)

    api_client = MzingaApiClient(
        base_url=str(config["api_base_url"]),
        email=str(config["admin_email"]),
        password=str(config["admin_password"]),
    )
    api_client.authenticate()

    logger.info(
        "worker_started",
        api=normalize_base_url(str(config["api_base_url"])),
        poll_interval_seconds=int(config["poll_interval_seconds"]),
    )

    poll_counter = telemetry["worker_poll_total"]

    while True:
        try:
            pending_docs = api_client.get_pending_communications()

            if not pending_docs:
                poll_counter.add(1, {"result": "empty"})
                time.sleep(int(config["poll_interval_seconds"]))
                continue

            poll_counter.add(1, {"result": "found"})

            for pending_doc in pending_docs:
                process_communication(
                    document=pending_doc,
                    api_client=api_client,
                    config=config,
                    telemetry=telemetry,
                    logger=logger,
                )

            time.sleep(int(config["poll_interval_seconds"]))
        except Exception as err:
            logger.error("poll_loop_error", error=str(err))
            time.sleep(int(config["poll_interval_seconds"]))


if __name__ == "__main__":
    main()
