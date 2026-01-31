"""
Voice Agent API endpoints.
Allows frontend to trigger calls and check status.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.models import User
from app.api.deps import get_current_user
from app.services.voice import trigger_call, get_call_status

router = APIRouter()


class CallRequest(BaseModel):
    phone_number: str  # E.164 format: +919876543210
    intent: str        # What should the AI say/achieve
    first_message: Optional[str] = None


class CallResponse(BaseModel):
    success: bool
    call_id: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None
    details: Optional[str] = None  # Full Vapi error response


@router.post("/call", response_model=CallResponse)
async def initiate_call(
    request: CallRequest,
    user: User = Depends(get_current_user)
):
    """
    Initiate an outbound voice call via Vapi.
    
    - **phone_number**: Target phone number in E.164 format (e.g., +919876543210)
    - **intent**: The objective/script for the AI caller
    - **first_message**: Optional custom opening line
    """
    # Validate phone number format
    if not request.phone_number.startswith("+"):
        raise HTTPException(
            status_code=400,
            detail="Phone number must be in E.164 format (e.g., +919876543210)"
        )
    
    print(f"[VOICE] Initiating call to {request.phone_number}")
    print(f"[VOICE] Intent: {request.intent[:100]}...")
    
    result = await trigger_call(
        phone_number=request.phone_number,
        intent=request.intent,
        first_message=request.first_message
    )
    
    print(f"[VOICE] Vapi Response: {result}")
    
    if result["success"]:
        # Log the call initiation
        print(f"[VOICE] User {user.clerk_id} initiated call to {request.phone_number}")
        print(f"[VOICE] Call ID: {result['call_id']}")
        
        return CallResponse(
            success=True,
            call_id=result["call_id"],
            status=result.get("status", "initiated")
        )
    else:
        # Log full error details
        print(f"[VOICE ERROR] {result.get('error')}")
        print(f"[VOICE ERROR DETAILS] {result.get('details')}")
        
        return CallResponse(
            success=False,
            error=result.get("error", "Unknown error"),
            details=result.get("details")
        )


@router.get("/call/{call_id}")
async def get_call_details(
    call_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get the status and transcript of a call.
    """
    result = await get_call_status(call_id)
    return result
