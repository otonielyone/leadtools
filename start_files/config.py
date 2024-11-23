# start_files/config.py
from fastapi.templating import Jinja2Templates
from typing import List, Dict, Union
from fastapi import Request
import os
from dotenv import load_dotenv

load_dotenv()


flash_messages = []

def flash(request: Request, message: str, category: str):
    """
    Store a flash message.
    """
    flash_messages.append({"message": message, "category": category})

def get_flashed_messages(request: Request) -> List[Dict[str, Union[str, List[str]]]]:
    """
    Retrieve all flash messages and clear them from the store.
    """
    messages = flash_messages[:]
    flash_messages.clear()
    return messages


def get_templates() -> Jinja2Templates:
    return Jinja2Templates(directory="start_files/templates")


SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///models/brightmls.db')


