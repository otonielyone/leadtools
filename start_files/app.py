from fastapi import Depends, FastAPI, HTTPException, Request
from start_files.config import get_templates
from start_files.routes.routes import router
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import logging
import os


load_dotenv()
ALLOWED_IPS = os.getenv("ALLOWED_IPS")

#
#class BlockApiMiddleware(BaseHTTPMiddleware):
#    async def dispatch(self, request: Request, call_next):
#        x_forwarded_for = request.headers.get("X-Forwarded-For")
#        if x_forwarded_for:
#            client_ip = x_forwarded_for.split(",")[0].strip()  
#        else:
#            client_ip = request.client.host  
#        logging.info(f"Request from IP: {client_ip}")
#        if any(request.url.path.startswith(path) for path in ["/api", "/docs", "/redoc"]):
#            if client_ip not in ALLOWED_IPS:
#                logging.warning(f"Access denied for IP: {client_ip}")
#                return RedirectResponse(url="/error")
#
#        response = await call_next(request)
#        return response


def create_app() -> FastAPI:
    app = FastAPI()
    #app.add_middleware(BlockApiMiddleware)
    app.mount("/static", StaticFiles(directory="start_files/static"), name="static")
    app.include_router(router)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/crm.log")
        ]
    )
    
    # Initialize state variables
    templates = get_templates()
    app.state.templates = templates
    
    return app