from enum import Enum
from typing import List
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from start_files.models.leads_db_section import (
    leads_sessionLocal, 
    Mls_leads, 
    get_notes_from_db, 
    save_notes_from_db, 
    delete_notes_from_db, 
    NoteResponse, 
    Possible_leads, 
    No_answer, 
    No_leads
)
from sqlalchemy.orm import class_mapper
from start_files.routes.leads_scripts import start_leads
from pydantic import BaseModel
import logging
import httpx
import os
from dotenv import load_dotenv

# Initialize the router
router = APIRouter()

# Load environment variables
load_dotenv()
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
RECIPIENT = os.getenv("RECIPIENT")
SENDER = os.getenv("SENDER")
MAILJET_API = os.getenv("MAILJET_API")
MAILJET_SECRET = os.getenv("MAILJET_SECRET")
GA_VIEW_ID = os.getenv("GA_VIEW_ID")
ALLOWED_IPS = os.getenv("ALLOWED_IPS")

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


########################################
############ GENERAL ROUTES ############
########################################

# Home route (proxy to external URL)
@router.get("/idx")
async def home_search(request: Request):
    external_url = "https://otonielyone.unitedrealestatewashingtondc.com/index.htm"
    async with httpx.AsyncClient() as client:
        response = await client.get(external_url)
        return StreamingResponse(
            content=response.aiter_raw(),
            headers=dict(response.headers),
            status_code=response.status_code
        )

# Error page route
@router.get("/error", response_class=HTMLResponse)
async def error_page(request: Request):
    return """
    <html>
        <head>
            <style>
                body {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    font-family: Arial, sans-serif;
                }
                h1 {
                    text-align: center;
                }
                p {
                    text-align: center;
                }
            </style>
        </head>
        <body>
            <div>
                <h1>Sorry, Access Denied</h1>
                <p>You do not have permission to access this page.</p>
            </div>
        </body>
    </html>
    """

# Route to view leads from MLS and CRM databases
@router.get("/", response_class=HTMLResponse)
@router.get("/leads", response_class=HTMLResponse)
async def view_leads(request: Request):
    with leads_sessionLocal() as db:
        leads_db = db.query(Mls_leads).all()
        leads = [{
            'ID': lead.id,
            'MLS': lead.mls,
            'Status': lead.status,
            'Sale_Amount': lead.sale_amt,
            'List_Price': lead.list_price,
            'Owner_Phone': lead.owner_phone,
            'Owner_Name': lead.owner_name,
            'Owner_Names': lead.owner_names,
            'Owner_Last_Name': lead.owner_last_name,
            'Owner_First_Name': lead.owner_first_name,
            'Owner2_Last_Name': lead.owner2_last_name,
            'Owner_Address': f"{lead.owner_address} {lead.owner_city_state or ''}, {lead.owner_zip_code or ''}",
            'Owner_Occupied': 'Yes' if lead.owner_occupied == 'Yes' else 'No',
            'Property_Class': lead.property_class,
            'Ownership': lead.ownership,
            'Listing_Agreement_Type': lead.listing_agreement_type,
            'Agent_Name': f"{lead.list_agent_first_name or ''} {lead.list_agent_last_name or ''}",
            'Office_Name': lead.list_office_name,
            'Remarks': lead.remarks_private,
            'Notes': lead.notes,
        } for lead in leads_db]

        possible_leads_data = db.query(Possible_leads).all()
        possible_entries = [{
            'customer_id':entry.id,
            'customer_mls':entry.mls,
            'customer_name': entry.name,
            'customer_phone': entry.phone,
            'customer_email': entry.email,
            'customer_address': entry.address,
            'customer_notes': entry.notes,
        } for entry in possible_leads_data]

        no_answer_data = db.query(No_answer).all()
        no_answer_entries = [{
            'customer_id':entry.id,
            'customer_mls':entry.mls,
            'customer_name': entry.name,
            'customer_phone': entry.phone,
            'customer_email': entry.email,
            'customer_address': entry.address,
            'customer_notes': entry.notes,
        } for entry in no_answer_data]

        no_leads_data = db.query(No_leads).all()
        no_leads_entries = [{
            'customer_id':entry.id,
            'customer_mls':entry.mls,
            'customer_name': entry.name,
            'customer_phone': entry.phone,
            'customer_email': entry.email,
            'customer_address': entry.address,
            'customer_notes': entry.notes,
        } for entry in no_leads_data]

    templates = request.app.state.templates
    return templates.TemplateResponse("leads.html", {"request": request, "leads": leads, "possible_entries": possible_entries, "no_answer_entries": no_answer_entries,"no_leads_entries": no_leads_entries})

# Route to get section data dynamically for a given section
@router.get("/get_section_data")
async def get_section_data(section: str):
    with leads_sessionLocal() as db:
        if section == 'possible_leads':
            entries = db.query(Possible_leads).all()
        elif section == 'no_leads':
            entries = db.query(No_leads).all()
        elif section == 'no_answer':
            entries = db.query(No_answer).all()
        else:
            raise HTTPException(status_code=400, detail="Invalid section")

        # Return the data in a suitable format for frontend
        return [{
            'id': entry.id,
            'mls': entry.mls,
            'name': entry.name,
            'phone': entry.phone,
            'email': entry.email,
            'address': entry.address,
            'notes': entry.notes or ''
        } for entry in entries]


# API to start MLS leads data gathering in the background
@router.get("/api/populate_leads_database", response_model=dict, name="import_leads")
async def get_leads_data(background_tasks: BackgroundTasks, request: Request, concurrency_limit: int = 10, max_retries: int = 20, delay: int=1):
    logger.info("Starting MLS leads gathering task")
    background_tasks.add_task(start_leads, concurrency_limit, max_retries, delay)
    return JSONResponse(content={"message": "MLS data gathering leads task started in the background"})


#####################################
############ NOTES ROUTE ############
#####################################

# Route to fetch notes for a given MLS
@router.post("/get_notes", response_model=NoteResponse)
async def get_notes(request: Request): 
    data = await request.json()
    logger.info(f"Received data: {data}")
    
    if not isinstance(data, dict) or 'mls' not in data:
        raise HTTPException(status_code=400, detail='Invalid data format or missing MLS')
    
    notes_data = get_notes_from_db(data)
    logger.info(notes_data)
    
    if notes_data:
        clean_notes = [note.notes.replace('\n', ' ').strip() for note in notes_data]
        return {"notes": clean_notes}
    
    return {"notes": []}

# Route to save notes in the database
@router.post("/save_notes")
async def save_notes(request: Request):
    data = await request.json()
    logger.info(f"Received data: {data}")  
    
    if not isinstance(data, dict) or 'mls' not in data:
        raise HTTPException(status_code=400, detail='Invalid data format or missing MLS')
    
    saved_data = save_notes_from_db(data)
    return saved_data

# Route to delete notes from the database
@router.post("/delete_notes")  
async def delete_notes(request: Request):
    data = await request.json()
    logger.info(f"Received data: {data}") 

    if not isinstance(data, dict) or 'mls' not in data:
        raise HTTPException(status_code=400, detail='Invalid data format or missing MLS')

    response = delete_notes_from_db(data)

    if response: 
        return {"message": "Notes deleted successfully", "data": response}
    else:
   
        raise HTTPException(status_code=404, detail='Notes not found or could not be deleted')

###################################
############ CRM ROUTES ##########
###################################
# Define Pydantic models for request and response validation
class ContactCreate(BaseModel):
    id: int
    mls: str
    owner_names: str
    owner_phone: str
    owner_email: str
    owner_address: str
    owner_notes: str

class ContactResponse(BaseModel):
    message: str

@router.post("/create_entry", response_model=ContactResponse)
async def create_entry(contact: ContactCreate, section: str):
    logger.info(f"Received data: {contact.model_dump()}, section: {section}")  
    
    if section == 'possible_leads':
        section = Possible_leads
    elif section == 'no_leads': 
        section = No_leads
    elif section == 'no_answer': 
        section = No_answer
    
    try:
        saved_data = save_data(contact.model_dump(), section) 
        return saved_data
    except Exception as e:
        logger.error(f"Error saving possible lead: {e}")
        raise HTTPException(status_code=500, detail="Failed to save possible lead")
    
def save_data(data: dict, section):
    # Extract fields from the data dictionary
    id = data.get('id')
    mls = data.get('mls')
    name = data.get('owner_names')
    phone = data.get('owner_phone')
    email = data.get('owner_email')
    address = data.get('owner_address')
    notes = data.get('owner_notes')
    
    if not name:
        raise HTTPException(status_code=400, detail="Name is required for the lead")

    with leads_sessionLocal() as db:
        # Check if the lead exists based on 'name'
        lead = db.query(section).filter_by(name=name).first()  # Query using the model class (section)

        if lead:
            # Update the lead if it exists
            lead.id = id if id else lead.id
            lead.mls = mls if mls else lead.mls
            lead.name = name if name and name.strip() else lead.name
            lead.phone = phone if phone and phone.strip() else lead.phone
            lead.email = email if email and email.strip() else lead.email
            lead.address = address if address and address.strip() else lead.email
            lead.notes = f"{lead.notes}\n{notes}" if notes else lead.notes
            db.commit()
            return {'message': f'{section.__tablename__} information updated successfully'}
        else:
            # Create a new lead if it doesn't exist
            new_lead = section(id=id, mls=mls, name=name, phone=phone, email=email, address=address, notes=notes)  # Pass the model class
            db.add(new_lead)
            db.commit()
            return {'message': f'{section.__tablename__} information saved successfully'}



# Update sections to match the JavaScript code
class AddToKvCoreRequest(BaseModel):
    ids: List[int]
    section: str

    class Config:
        schema_extra = {
            "example": {
                "ids": [1, 2, 3],
                "section": "possible-lead"
            }
        }


def serialize_sqlalchemy_obj(obj):
    return {col.key: getattr(obj, col.key) for col in class_mapper(obj.__class__).columns}

@router.post("/add_to_kvcore")
async def add_to_kvcore(request: AddToKvCoreRequest):            
    try:
        with leads_sessionLocal() as db:
            variables = []
            table = None

            if 'possible_leads' in request.section:
                table = Possible_leads
            elif 'no_leads' in request.section:
                table = No_leads
            elif 'no_answer' in request.section:
                table = No_answer
            if not table:
                raise ValueError(f"Invalid section: {request.section}")
            for id in request.ids:
                id_found = db.query(table).filter_by(id=id).first()
                
                if id_found:
                    variables.append(serialize_sqlalchemy_obj(id_found))
                    db.delete(id_found) 
                else:
                    logger.warning(f"ID {id} not found in {request.section}")
            db.commit()
            data = {key: value for d in variables for key, value in d.items()}
            logger.info(f"Successfully added {data} to KVCore")
            return {"status": "success"}
    except Exception as e:
        logger.error(f"Error adding entries to KVCore: {str(e)}")
        return {"status": "error", "message": str(e)}


@router.post("/delete_entries")
async def delete_entries(request: AddToKvCoreRequest):
    try:
        logger.info(
            f"Deleting entries - Section: {request.section}, "
            f"Ids: {request.ids}"
        )
        with leads_sessionLocal() as db:
            if request.section == 'possible_leads':
                table = Possible_leads
            elif request.section == 'no_leads':
                table = No_leads
            elif request.section == 'no_answer':
                table = No_answer
            else:
                raise ValueError(f"Invalid section: {request.section}")

            deleted_ids = []
            not_found_ids = []

            for id in request.ids:
                id_found = db.query(table).filter_by(id=id).first()
                if id_found:
                    db.delete(id_found)
                    deleted_ids.append(id)
                else:
                    not_found_ids.append(id)

            db.commit()

        messages = []
        if deleted_ids:
            messages.append(f"Deleted entries: {', '.join(map(str, deleted_ids))}")
        if not_found_ids:
            messages.append(f"No entries found for IDs: {', '.join(map(str, not_found_ids))}")

        return {
            "status": "success",
            "message": " ".join(messages) if messages else "No action performed."
        }
    except Exception as e:
        logger.error(f"Error deleting entries: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Error occurred: {str(e)}"
        }
