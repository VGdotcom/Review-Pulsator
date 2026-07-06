"""
MCP Delivery & Workspace Integration Module (Phase 5).
Handles formatting and publishing of the WeeklyPulseReport to Google Docs and Gmail
via Model Context Protocol (MCP) tool calls, with robust fallback archiving and retry resilience.
"""
import os
import json
import time
import logging
from typing import Any, Callable, Dict, Optional
from review_pulsator.config import PulsatorConfig
from review_pulsator.schemas import WeeklyPulseReport

logger = logging.getLogger("review_pulsator.delivery")


class MCPIntegrationService:
    """
    Service responsible for publishing weekly pulse reports to Google Workspace (Docs & Gmail)
    using MCP tool abstractions, enforcing exponential backoff and offline filesystem fallback.
    """

    def __init__(
        self,
        config: Optional[PulsatorConfig] = None,
        mcp_tool_caller: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
        retry_delays: Optional[list] = None,
    ):
        """
        Initialize the MCP integration service.
        :param config: PulsatorConfig instance.
        :param mcp_tool_caller: Callable function taking (tool_name, arguments) -> dict result.
        :param retry_delays: List of retry delay seconds for exponential backoff (default: [2, 4, 8]).
        """
        self.config = config or PulsatorConfig.from_env()
        self.mcp_tool_caller = mcp_tool_caller
        self.retry_delays = retry_delays if retry_delays is not None else [2, 4, 8]

    def format_for_gdocs(self, report: WeeklyPulseReport) -> str:
        """
        Convert WeeklyPulseReport into structured Markdown/Text suitable for Google Docs creation or append.
        """
        lines = [
            f"# 🛵 Swiggy Weekly Pulse Report ({report.report_date})",
            f"**Total Word Count:** {report.word_count} / {self.config.word_count_ceiling} words\n",
            "## 📌 Top Emerging Sentiment Themes",
        ]
        for idx, t in enumerate(report.top_themes, 1):
            lines.append(f"### {idx}. {t.name}\n{t.summary}\n")

        lines.append("## 💬 Verbatim Customer Quotes")
        for q in report.verbatim_quotes:
            lines.append(f'> "{q}"\n')

        lines.append("## 🎯 Recommended Action Ideas")
        for idx, a in enumerate(report.action_ideas, 1):
            lines.append(f"{idx}. {a}")

        return "\n".join(lines)

    def format_for_gmail(self, report: WeeklyPulseReport, doc_url: str) -> str:
        """
        Convert WeeklyPulseReport into a clean HTML summary formatted for a Gmail notification draft.
        """
        themes_html = ""
        for idx, t in enumerate(report.top_themes, 1):
            themes_html += f"<li style='margin-bottom: 10px;'><strong>{t.name}:</strong> {t.summary}</li>"

        actions_html = ""
        for idx, a in enumerate(report.action_ideas, 1):
            actions_html += f"<li style='margin-bottom: 5px;'>{a}</li>"

        html = f"""<div style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 650px;">
  <h2 style="color: #fc8019; border-bottom: 2px solid #fc8019; padding-bottom: 8px;">
    🛵 Swiggy Weekly Pulse Report ({report.report_date})
  </h2>
  <p>Here is your executive summary of top emerging customer feedback themes and recommended product actions from the past week:</p>
  
  <h3 style="color: #2c3e50;">📌 Top Emerging Themes</h3>
  <ul>
    {themes_html}
  </ul>

  <h3 style="color: #2c3e50;">🎯 Recommended Engineering & Product Actions</h3>
  <ol>
    {actions_html}
  </ol>

  <div style="margin: 25px 0; text-align: center;">
    <a href="{doc_url}" style="background-color: #fc8019; color: white; padding: 12px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
      📄 View Full Styled Report in Google Docs
    </a>
  </div>

  <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
  <p style="font-size: 0.85em; color: #7f8c8d;">
    Generated automatically by Review Pulsator AI Engine (Word Count: {report.word_count} / {self.config.word_count_ceiling} words).
  </p>
</div>"""
        return html

    def _default_cloud_mcp_caller(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Default HTTP Streamable MCP client that connects to the cloud Hugging Face Spaces endpoint.
        Used automatically when no external mcp_tool_caller callback is provided.
        """
        import urllib.request
        import ssl
        
        url = "https://vgdotcom-google-workspace-mcp.hf.space/sse"
        ctx = ssl._create_unverified_context()
        
        # Map legacy/generic tool names and schemas to the verified cloud MCP tools
        actual_tool = tool_name
        actual_args = dict(arguments)
        
        if tool_name in ("mcp_gdocs_update_doc", "mcp_gdocs_create_doc", "append_content"):
            actual_tool = "append_content"
            if "doc_id" in actual_args and "document_id" not in actual_args:
                actual_args["document_id"] = actual_args.pop("doc_id")
            if "document_id" not in actual_args or not actual_args["document_id"]:
                if self.config.gdocs_doc_id:
                    actual_args["document_id"] = self.config.gdocs_doc_id
                else:
                    raise ValueError("No Google Document ID provided for append_content.")
                    
        elif tool_name in ("mcp_gmail_create_draft", "draft_email"):
            actual_tool = "draft_email"
            target_to = actual_args.pop("to", self.config.target_email)
            if isinstance(target_to, str):
                target_to = [target_to] if target_to else []
            actual_args["to"] = target_to
            if "body" not in actual_args or not actual_args["body"]:
                actual_args["body"] = "Please view the Swiggy Weekly Pulse Report attached or via link."
            if "is_html" in actual_args:
                actual_args.pop("is_html")
            if "html" not in actual_args and "<div" in str(actual_args.get("body", "")):
                actual_args["html"] = actual_args["body"]
                actual_args["body"] = "Please view the HTML formatted Swiggy Weekly Pulse Report in this draft."

        logger.info(f"Connecting to remote cloud MCP endpoint ({url}) for tool '{actual_tool}'...")
        
        # Step 1: Initialize session
        init_payload = json.dumps({
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "review_pulsator", "version": "0.1.0"}
            }
        }).encode("utf-8")
        
        req = urllib.request.Request(
            url,
            data=init_payload,
            headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        )
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            session_id = resp.headers.get("mcp-session-id")
            if not session_id:
                raise RuntimeError("Failed to obtain mcp-session-id from cloud MCP server initialization.")
                
        # Step 2: Call tool
        call_payload = json.dumps({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 2,
            "params": {
                "name": actual_tool,
                "arguments": actual_args
            }
        }).encode("utf-8")
        
        req2 = urllib.request.Request(
            url,
            data=call_payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "mcp-session-id": session_id
            }
        )
        with urllib.request.urlopen(req2, context=ctx, timeout=30) as resp2:
            body_bytes = resp2.read().decode("utf-8")
            for line in body_bytes.splitlines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    try:
                        res_json = json.loads(data_str)
                        if "error" in res_json:
                            raise RuntimeError(f"Cloud MCP Error: {res_json['error']}")
                        result_content = res_json.get("result", {}).get("content", [])
                        if result_content and isinstance(result_content, list):
                            text_res = result_content[0].get("text", "{}")
                            try:
                                return json.loads(text_res)
                            except Exception:
                                return {"raw_result": text_res}
                        return res_json.get("result", {})
                    except json.JSONDecodeError:
                        continue
            return {"status": "success", "raw": body_bytes}

    def _call_mcp_tool_with_retry(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke an MCP tool with exponential backoff retry resilience (Edge Case 5.1).
        """
        caller = self.mcp_tool_caller or self._default_cloud_mcp_caller

        last_error = None
        attempts = len(self.retry_delays) + 1

        for attempt in range(1, attempts + 1):
            try:
                logger.info(f"Invoking MCP tool '{tool_name}' (Attempt {attempt}/{attempts})...")
                result = caller(tool_name, arguments)
                if result and isinstance(result, dict) and result.get("error"):
                    raise RuntimeError(f"MCP Tool Error: {result['error']}")
                return result or {}
            except Exception as e:
                last_error = e
                logger.warning(f"MCP tool '{tool_name}' failed on attempt {attempt}: {str(e)}")
                if attempt < attempts:
                    delay = self.retry_delays[attempt - 1]
                    logger.info(f"Backing off for {delay} seconds before retry...")
                    if delay > 0:
                        time.sleep(delay)

        raise RuntimeError(f"Exhausted all {attempts} retry attempts for MCP tool '{tool_name}': {str(last_error)}")

    def _archive_offline_fallback(self, report: WeeklyPulseReport, gdocs_content: str, gmail_content: str, reason: str) -> str:
        """
        Save delivery package to filesystem archive when MCP server is unreachable or degraded (Edge Case 5.1).
        """
        archive_dir = os.path.join(self.config.archive_dir, "failed_mcp_delivery")
        os.makedirs(archive_dir, exist_ok=True)
        
        timestamp = report.report_date
        json_path = os.path.join(archive_dir, f"pulse_{timestamp}.json")
        md_path = os.path.join(archive_dir, f"pulse_{timestamp}.md")
        html_path = os.path.join(archive_dir, f"pulse_{timestamp}_email.html")

        archive_payload = {
            "report_date": report.report_date,
            "delivery_status": "DEGRADED_OFFLINE_ARCHIVE",
            "degradation_reason": reason,
            "report_payload": report.model_dump(),
            "gdocs_markdown": gdocs_content,
            "gmail_html": gmail_content,
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(archive_payload, f, indent=2)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(gdocs_content)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(gmail_content)

        logger.error(f"ADMIN ALERT: MCP delivery degraded ({reason}). Offline archive saved to: {json_path}")
        print(f"\n[ADMIN ALERT] ⚠️ MCP Delivery Degraded: {reason}")
        print(f"[ADMIN ALERT] 📂 Saved offline backup archive to: {json_path}\n")
        return json_path

    def deliver_report(
        self,
        report: WeeklyPulseReport,
        target_email: Optional[str] = None,
        doc_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute end-to-end MCP delivery: publish/update Google Doc and create Gmail draft.
        Returns a structured summary of delivery status and resource URIs.
        """
        target_email = target_email or self.config.target_email
        doc_id = doc_id or self.config.gdocs_doc_id

        gdocs_content = self.format_for_gdocs(report)
        gdocs_status = "PENDING"
        doc_url = "[Offline Archive — MCP Unavailable]"
        result_doc_id = doc_id
        degradation_reasons = []

        # --- 1. Google Docs Publication ---
        try:
            if doc_id:
                # Edge Case 5.2: Try appending section to existing doc
                try:
                    logger.info(f"Attempting to update existing Google Doc ({doc_id}) via MCP...")
                    append_content = f"\n\n[Pulse Report — {report.report_date}]\n\n{gdocs_content}"
                    res = self._call_mcp_tool_with_retry("mcp_gdocs_update_doc", {"doc_id": doc_id, "content": append_content})
                    doc_url = res.get("doc_url") or f"https://docs.google.com/document/d/{doc_id}/edit"
                    gdocs_status = "SUCCESS"
                except Exception as update_err:
                    logger.warning(f"Failed to update existing doc {doc_id} ({str(update_err)}). Falling back to creating new doc.")
                    doc_id = None  # Trigger fallback creation below
            
            if not doc_id:
                logger.info("Creating new Google Doc via MCP...")
                title = f"Swiggy Weekly Pulse Report — {report.report_date}"
                res = self._call_mcp_tool_with_retry("mcp_gdocs_create_doc", {"title": title, "content": gdocs_content})
                result_doc_id = res.get("doc_id", "unknown_doc_id")
                doc_url = res.get("doc_url") or f"https://docs.google.com/document/d/{result_doc_id}/edit"
                gdocs_status = "SUCCESS"

        except Exception as gdocs_err:
            gdocs_status = "FAILED"
            err_str = f"Google Docs MCP failure: {str(gdocs_err)}"
            logger.error(err_str)
            degradation_reasons.append(err_str)

        # --- 2. Gmail Draft Creation ---
        gmail_content = self.format_for_gmail(report, doc_url)
        gmail_status = "PENDING"
        draft_id = None

        try:
            logger.info(f"Creating Gmail notification draft addressed to '{target_email}' via MCP...")
            subject = f"🛵 Swiggy Weekly Pulse Report — {report.report_date}"
            try:
                res = self._call_mcp_tool_with_retry(
                    "mcp_gmail_create_draft",
                    {"to": target_email, "subject": subject, "body": gmail_content, "is_html": True}
                )
                draft_id = res.get("draft_id", "created_draft")
                gmail_status = "SUCCESS"
            except Exception as email_err:
                # Edge Case 5.3: If target email alias fails validation/quota, try defaulting without explicit 'to' (self-addressed draft)
                logger.warning(f"Draft creation for '{target_email}' failed ({str(email_err)}). Retrying as self-addressed draft...")
                res = self._call_mcp_tool_with_retry(
                    "mcp_gmail_create_draft",
                    {"subject": subject, "body": gmail_content, "is_html": True}
                )
                draft_id = res.get("draft_id", "self_addressed_draft")
                gmail_status = "SUCCESS"

        except Exception as gmail_err:
            gmail_status = "FAILED"
            err_str = f"Gmail MCP failure: {str(gmail_err)}"
            logger.error(err_str)
            degradation_reasons.append(err_str)

        # --- 3. Resilience & Offline Fallback Archiving ---
        archive_path = None
        overall_status = "SUCCESS"

        if gdocs_status == "FAILED" or gmail_status == "FAILED":
            overall_status = "DEGRADED"
            reason_str = " ; ".join(degradation_reasons)
            archive_path = self._archive_offline_fallback(report, gdocs_content, gmail_content, reason_str)
        else:
            # Optionally save a routine successful copy to archives
            normal_archive_dir = os.path.join(self.config.archive_dir, "delivered_reports")
            os.makedirs(normal_archive_dir, exist_ok=True)
            archive_path = os.path.join(normal_archive_dir, f"pulse_{report.report_date}.json")
            with open(archive_path, "w", encoding="utf-8") as f:
                json.dump({
                    **report.model_dump(),
                    "status": "SUCCESS",
                    "doc_id": result_doc_id,
                    "doc_url": doc_url,
                    "draft_id": draft_id,
                    "target_email": target_email,
                }, f, indent=2)

        return {
            "status": overall_status,
            "gdocs_status": gdocs_status,
            "gmail_status": gmail_status,
            "doc_id": result_doc_id,
            "doc_url": doc_url,
            "draft_id": draft_id,
            "target_email": target_email,
            "archive_path": archive_path,
            "degradation_reasons": degradation_reasons,
        }
