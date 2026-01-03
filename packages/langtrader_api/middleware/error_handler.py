"""
Global Exception Handlers
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from datetime import datetime
import traceback

from langtrader_api.config import settings


def setup_exception_handlers(app: FastAPI):
    """Setup global exception handlers for the FastAPI app"""
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.detail,
                "code": f"HTTP_{exc.status_code}",
                "timestamp": datetime.now().isoformat(),
            },
            headers=exc.headers,
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle request validation errors"""
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            })
        
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": "Validation Error",
                "detail": errors,
                "code": "VALIDATION_ERROR",
                "timestamp": datetime.now().isoformat(),
            },
        )
    
    @app.exception_handler(ValidationError)
    async def pydantic_validation_handler(request: Request, exc: ValidationError):
        """Handle Pydantic validation errors"""
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": "Data Validation Error",
                "detail": exc.errors(),
                "code": "PYDANTIC_VALIDATION_ERROR",
                "timestamp": datetime.now().isoformat(),
            },
        )
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """Handle value errors"""
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": str(exc),
                "code": "VALUE_ERROR",
                "timestamp": datetime.now().isoformat(),
            },
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle all other exceptions"""
        # Log the full traceback
        if settings.DEBUG:
            traceback.print_exc()
        
        # Return generic error in production
        detail = str(exc) if settings.DEBUG else "An unexpected error occurred"
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal Server Error",
                "detail": detail,
                "code": "INTERNAL_ERROR",
                "timestamp": datetime.now().isoformat(),
            },
        )

