"""
Webhook endpoints for external service callbacks.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

router = APIRouter()


class VapiWebhookPayload(BaseModel):
    """Vapi sends various event types via webhook."""
    type: str  # "call-started", "call-ended", "transcript", etc.
    call: Optional[Dict[str, Any]] = None
    message: Optional[Dict[str, Any]] = None


@router.post("/vapi")
async def vapi_webhook(request: Request):
    """
    Handle Vapi webhook callbacks.
    
    Events:
    - call-started: Call has been initiated
    - call-ended: Call completed, includes transcript/summary
    - transcript: Real-time transcript updates
    """
    try:
        payload = await request.json()
        event_type = payload.get("type", payload.get("message", {}).get("type", "unknown"))
        
        print(f"[VAPI WEBHOOK] Received event: {event_type}")
        print(f"[VAPI WEBHOOK] Payload: {payload}")
        
        # Handle call-ended event (most important)
        if event_type == "end-of-call-report":
            call_data = payload.get("call", {}) or payload
            
            call_id = call_data.get("id")
            transcript = call_data.get("transcript")
            summary = call_data.get("summary")
            duration = call_data.get("duration")
            status = call_data.get("status")
            
            # Log the result
            from app.models import MissionLog
            
            # Store as a mission log (if we have mission context)
            # For now, just print
            print(f"[VAPI] Call {call_id} ended.")
            print(f"[VAPI] Status: {status}")
            print(f"[VAPI] Duration: {duration} seconds")
            print(f"[VAPI] Summary: {summary}")
            print(f"[VAPI] Transcript: {transcript[:500] if transcript else 'N/A'}...")
            
            # Check for mission_id in metadata
            assistant_metadata = call_data.get("assistant", {}).get("metadata", {})
            # Also check top-level metadata just in case
            top_metadata = call_data.get("metadata", {})
            
            mission_id = assistant_metadata.get("mission_id") or top_metadata.get("mission_id")
            
            if mission_id:
                try:
                    # Import here to avoid circular dependency
                    from app.core.agent import log_event
                    from app.models import Mission
                    
                    mission = await Mission.get(mission_id)
                    user_id = mission.user_id if mission else "unknown"
                    
                    await log_event(
                        mission_id, 
                        user_id, 
                        f"📞 Call completed.\n\n**Summary:** {summary}\n\n**Duration:** {duration}s\n**Status:** {status}", 
                        "success",
                        metadata={"type": "voice_call", "call_id": call_id, "transcript": transcript}
                    )
                except Exception as ex:
                    print(f"[VAPI WEBHOOK] Failed to log to mission: {ex}")
            
            return {
                "status": "received",
                "call_id": call_id,
                "summary": summary
            }
        
        elif event_type == "status-update":
            status = payload.get("message", {}).get("status")
            print(f"[VAPI] Status update: {status}")
            return {"status": "acknowledged"}
        
        elif event_type == "transcript":
            # Real-time transcript
            transcript = payload.get("message", {}).get("transcript")
            print(f"[VAPI] Transcript update: {transcript}")
            return {"status": "acknowledged"}
        
        # Default acknowledgement
        return {"status": "received", "event": event_type}
        
    except Exception as e:
        print(f"[VAPI WEBHOOK ERROR] {e}")
        # Always return 200 to Vapi to avoid retries
        return {"status": "error", "message": str(e)}


@router.get("/vapi/health")
async def vapi_health():
    """Health check for webhook endpoint."""
    return {"status": "ok", "service": "vapi-webhook"}
