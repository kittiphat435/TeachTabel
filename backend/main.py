import os
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import firebase_admin
from firebase_admin import credentials, firestore
import io

app = FastAPI(title="TeachTabel API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ใน production ควรระบุ URL ของ frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Firebase Initialization
try:
    # Use relative path from the current file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cert_path = os.path.join(base_dir, "teachtable-84920-firebase-adminsdk-fbsvc-a1d054cf04.json")
    cred = credentials.Certificate(cert_path)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase initialized successfully")
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    db = None

# Pydantic Models for API
class Teacher(BaseModel):
    id: Optional[str] = None
    full_name: str
    department: str

class Subject(BaseModel):
    id: Optional[str] = None
    subject_code: str
    subject_name: str

class Classroom(BaseModel):
    id: Optional[str] = None
    grade_level: str
    room_name: str
    lunch_period: Optional[int] = None

class Room(BaseModel):
    id: Optional[str] = None
    room_name: str
    room_type: str

class UnavailabilityCreate(BaseModel):
    teacher_ids: List[str]
    day_of_week: int
    period_number: int
    reason: Optional[str] = "ไม่ว่าง"

class AssignmentCreate(BaseModel):
    subject_id: str
    teacher_ids: List[str]
    classroom_ids: List[str]
    total_periods: int
    period_split: List[int]
    term_id: Optional[str] = None
    room_id: Optional[str] = None

class FixedEventCreate(BaseModel):
    event_name: str
    day_of_week: int
    period_number: int
    classroom_ids: List[str]
    teacher_ids: Optional[List[str]] = []
    room_id: Optional[str] = None

# --- GET APIs (ดึงข้อมูลมาแสดงที่ Frontend) ---

@app.get("/fixed-events/")
async def get_fixed_events():
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        # ดึง Lookup tables
        classrooms_map = {doc.id: f"{doc.to_dict().get('grade_level')}/{doc.to_dict().get('room_name')}" for doc in db.collection("classrooms").stream()}
        teachers_map = {doc.id: doc.to_dict().get("full_name") for doc in db.collection("teachers").stream()}
        rooms_map = {doc.id: doc.to_dict().get("room_name") for doc in db.collection("rooms").stream()}

        events = []
        event_docs = db.collection("fixed_events").stream()
        for doc in event_docs:
            data = doc.to_dict()
            e_id = doc.id
            
            # ดึงผู้เข้าร่วม
            c_names = []
            t_names = []
            part_docs = db.collection("event_participants").where("event_id", "==", e_id).stream()
            for p in part_docs:
                p_data = p.to_dict()
                p_id = p_data.get("participant_id")
                if p_data.get("participant_type") == "classroom" and p_id in classrooms_map:
                    c_names.append(classrooms_map[p_id])
                elif p_data.get("participant_type") == "teacher" and p_id in teachers_map:
                    t_names.append(teachers_map[p_id])

            events.append({
                "id": e_id,
                "event_name": data.get("event_name"),
                "day_of_week": data.get("day_of_week"),
                "period_number": data.get("period_number"),
                "classroom_names": c_names,
                "teacher_names": t_names,
                "room_name": rooms_map.get(data.get("room_id"), "ไม่ระบุ")
            })
        return events
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/fixed-events/")
async def create_fixed_event(data: FixedEventCreate):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        event_data = {
            "event_name": data.event_name,
            "day_of_week": data.day_of_week,
            "period_number": data.period_number,
            "room_id": data.room_id
        }
        _, doc_ref = db.collection("fixed_events").add(event_data)
        event_id = doc_ref.id

        for c_id in data.classroom_ids:
            db.collection("event_participants").add({
                "event_id": event_id,
                "participant_type": "classroom",
                "participant_id": c_id
            })
        for t_id in data.teacher_ids:
            db.collection("event_participants").add({
                "event_id": event_id,
                "participant_type": "teacher",
                "participant_id": t_id
            })
        return {"status": "success", "event_id": event_id}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/fixed-events/{event_id}")
async def delete_fixed_event(event_id: str):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("fixed_events").document(event_id).delete()
        parts = db.collection("event_participants").where("event_id", "==", event_id).stream()
        for p in parts: p.reference.delete()
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/assignments/")
async def get_assignments():
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        teachers_map = {doc.id: doc.to_dict().get("full_name") for doc in db.collection("teachers").stream()}
        subjects_map = {doc.id: f"{doc.to_dict().get('subject_code')} {doc.to_dict().get('subject_name')}" for doc in db.collection("subjects").stream()}
        classrooms_map = {doc.id: f"{doc.to_dict().get('grade_level')}/{doc.to_dict().get('room_name')}" for doc in db.collection("classrooms").stream()}
        rooms_map = {doc.id: doc.to_dict().get("room_name") for doc in db.collection("rooms").stream()}

        assignments = []
        assign_docs = db.collection("assignments").stream()
        for doc in assign_docs:
            data = doc.to_dict()
            a_id = doc.id
            t_names = []
            t_rels = db.collection("assignment_teachers").where("assignment_id", "==", a_id).stream()
            for rel in t_rels:
                t_id = rel.to_dict().get("teacher_id")
                if t_id in teachers_map: t_names.append(teachers_map[t_id])
            c_names = []
            c_rels = db.collection("assignment_classrooms").where("assignment_id", "==", a_id).stream()
            for rel in c_rels:
                c_id = rel.to_dict().get("classroom_id")
                if c_id in classrooms_map: c_names.append(classrooms_map[c_id])
            assignments.append({
                "id": a_id,
                "subject_name": subjects_map.get(data.get("subject_id"), "ไม่ทราบวิชา"),
                "teacher_names": t_names,
                "classroom_names": c_names,
                "room_name": rooms_map.get(data.get("room_id"), "ไม่ระบุ"),
                "total_periods": data.get("total_periods"),
                "period_split": data.get("period_split")
            })
        return assignments
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/assignments/")
async def create_assignment(data: AssignmentCreate):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        assignment_data = {
            "subject_id": data.subject_id,
            "total_periods": data.total_periods,
            "period_split": data.period_split,
            "term_id": data.term_id,
            "room_id": data.room_id
        }
        _, doc_ref = db.collection("assignments").add(assignment_data)
        assignment_id = doc_ref.id
        for t_id in data.teacher_ids:
            db.collection("assignment_teachers").add({"assignment_id": assignment_id, "teacher_id": t_id})
        for c_id in data.classroom_ids:
            db.collection("assignment_classrooms").add({"assignment_id": assignment_id, "classroom_id": c_id})
        return {"status": "success", "assignment_id": assignment_id}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- Teacher Unavailability APIs ---

@app.get("/unavailabilities/")
async def get_all_unavailabilities():
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        teachers_map = {doc.id: doc.to_dict().get("full_name") for doc in db.collection("teachers").stream()}
        docs = db.collection("teacher_unavailabilities").stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            t_id = data.get("teacher_id")
            results.append({
                "id": doc.id,
                "teacher_name": teachers_map.get(t_id, "ไม่ทราบชื่อ"),
                "day_of_week": data.get("day_of_week"),
                "period_number": data.get("period_number"),
                "reason": data.get("reason")
            })
        return results
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/unavailabilities/")
async def create_unavailabilities(data: UnavailabilityCreate):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        for t_id in data.teacher_ids:
            db.collection("teacher_unavailabilities").add({
                "teacher_id": t_id,
                "day_of_week": data.day_of_week,
                "period_number": data.period_number,
                "reason": data.reason
            })
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/unavailabilities/{doc_id}")
async def delete_unavailability(doc_id: str):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("teacher_unavailabilities").document(doc_id).delete()
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/teachers/{teacher_id}/assignments")
async def get_teacher_assignments(teacher_id: str):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        rel_docs = db.collection("assignment_teachers").where("teacher_id", "==", teacher_id).stream()
        a_ids = [rel.to_dict().get("assignment_id") for rel in rel_docs]
        if not a_ids: return []
        subjects_map = {doc.id: f"{doc.to_dict().get('subject_code')} {doc.to_dict().get('subject_name')}" for doc in db.collection("subjects").stream()}
        classrooms_map = {doc.id: f"{doc.to_dict().get('grade_level')}/{doc.to_dict().get('room_name')}" for doc in db.collection("classrooms").stream()}
        teacher_assignments = []
        for a_id in a_ids:
            a_doc = db.collection("assignments").document(a_id).get()
            if a_doc.exists:
                data = a_doc.to_dict()
                c_names = []
                c_rels = db.collection("assignment_classrooms").where("assignment_id", "==", a_id).stream()
                for c_rel in c_rels:
                    c_id = c_rel.to_dict().get("classroom_id")
                    if c_id in classrooms_map: c_names.append(classrooms_map[c_id])
                teacher_assignments.append({
                    "id": a_id,
                    "subject_name": subjects_map.get(data.get("subject_id"), "ไม่ทราบวิชา"),
                    "classroom_names": c_names,
                    "total_periods": data.get("total_periods"),
                    "period_split": data.get("period_split")
                })
        return teacher_assignments
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/teachers/", response_model=List[Teacher])
async def get_teachers():
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    docs = db.collection("teachers").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

@app.get("/subjects/", response_model=List[Subject])
async def get_subjects():
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    docs = db.collection("subjects").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

@app.get("/classrooms/", response_model=List[Classroom])
async def get_classrooms():
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    docs = db.collection("classrooms").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

@app.get("/rooms/", response_model=List[Room])
async def get_rooms():
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    docs = db.collection("rooms").stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]

@app.post("/classrooms/manual")
async def create_classroom_manual(data: Classroom):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("classrooms").add(data.model_dump(exclude={"id"}))
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/rooms/manual")
async def create_room_manual(data: Room):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("rooms").add(data.model_dump(exclude={"id"}))
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/subjects/manual")
async def create_subject_manual(data: Subject):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("subjects").add(data.model_dump(exclude={"id"}))
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/teachers/manual")
async def create_teacher_manual(data: Teacher):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("teachers").add(data.model_dump(exclude={"id"}))
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- IMPORT APIs ---

@app.post("/import/rooms/")
async def import_rooms(file: UploadFile = File(...)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        count = 0
        for _, row in df.iterrows():
            db.collection("rooms").add({"room_name": str(row['room_name']), "room_type": str(row['room_type']) if 'room_type' in row else "ห้องเรียนประจำ"})
            count += 1
        return {"status": "success", "imported_count": count}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/import/teachers/")
async def import_teachers(file: UploadFile = File(...)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        count = 0
        for _, row in df.iterrows():
            db.collection("teachers").add({"full_name": row['full_name'], "department": row['department']})
            count += 1
        return {"status": "success", "imported_count": count}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/import/subjects/")
async def import_subjects(file: UploadFile = File(...)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        count = 0
        for _, row in df.iterrows():
            db.collection("subjects").add({"subject_code": str(row['subject_code']), "subject_name": row['subject_name']})
            count += 1
        return {"status": "success", "imported_count": count}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/import/classrooms/")
async def import_classrooms(file: UploadFile = File(...)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        count = 0
        for _, row in df.iterrows():
            db.collection("classrooms").add({"grade_level": str(row['grade_level']), "room_name": str(row['room_name'])})
            count += 1
        return {"status": "success", "imported_count": count}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
