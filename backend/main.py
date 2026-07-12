import os
import re
import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import firebase_admin
from firebase_admin import credentials, firestore, auth as fb_auth
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

# --- Auth (Firebase Google Sign-In) ---
# Frontend เข้าสู่ระบบด้วย Firebase Auth (Google) แล้วแนบ ID token มาใน header
# Authorization: Bearer <idToken> ทุก request ที่ต้องแก้ไขข้อมูล

bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    """ตรวจสอบ Firebase ID token และคืนค่าโปรไฟล์ผู้ใช้ (สร้างอัตโนมัติถ้ายังไม่มี)"""
    if not db:
        raise HTTPException(status_code=500, detail="Firestore not initialized")
    if credentials is None:
        raise HTTPException(status_code=401, detail="กรุณาเข้าสู่ระบบก่อนใช้งาน (Login required)")
    try:
        decoded = fb_auth.verify_id_token(credentials.credentials)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token ไม่ถูกต้องหรือหมดอายุ: {e}")

    uid = decoded["uid"]
    user_ref = db.collection("users").document(uid)
    user_doc = user_ref.get()
    if not user_doc.exists:
        # ผู้ใช้คนแรกของระบบจะได้สิทธิ์ admin โดยอัตโนมัติ ที่เหลือเป็น teacher (ปรับสิทธิ์ทีหลังได้)
        is_first_user = len(list(db.collection("users").limit(1).stream())) == 0
        user_data = {
            "email": decoded.get("email"),
            "name": decoded.get("name") or decoded.get("email"),
            "picture": decoded.get("picture"),
            "role": "admin" if is_first_user else "teacher",
        }
        user_ref.set(user_data)
    else:
        user_data = user_doc.to_dict()
    return {"uid": uid, **user_data}

async def require_admin(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="ต้องเป็นผู้ดูแลระบบ (admin) เท่านั้น")
    return user

def _read_table(contents: bytes, filename: str) -> pd.DataFrame:
    """อ่านไฟล์นำเข้าได้ทั้ง .csv และ .xlsx/.xls
    บังคับอ่านทุกคอลัมน์เป็น string (dtype=str) เพราะไม่ทำแบบนี้ pandas จะเดาว่าคอลัมน์รหัส/ตัวเลข
    เป็นตัวเลขแล้วตัดเลข 0 ข้างหน้าทิ้งเอง (เช่น รหัสครู '0406' จะกลายเป็น 406) ทำให้ข้อมูลผิดเพี้ยน"""
    name = (filename or "").lower()
    if name.endswith(".csv"):
        try:
            return pd.read_csv(io.BytesIO(contents), dtype=str, keep_default_na=True)
        except UnicodeDecodeError:
            return pd.read_csv(io.BytesIO(contents), encoding="utf-8-sig", dtype=str, keep_default_na=True)
    return pd.read_excel(io.BytesIO(contents), dtype=str)

def _natural_key(s):
    """key สำหรับเรียงลำดับแบบธรรมชาติ (natural sort) เช่น '1/2' มาก่อน '1/12'
    แทนที่จะเรียงแบบ string ปกติที่จะได้ '1/1','1/10','1/11','1/12','1/2',... ซึ่งผิดธรรมชาติ"""
    s = "" if s is None else str(s)
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

def _get_col(row, *names, default: str = "") -> str:
    """อ่านค่าคอลัมน์จากไฟล์นำเข้า รองรับชื่อคอลัมน์ได้หลายแบบ (เผื่อผู้ใช้ตั้งชื่อหัวตารางต่างกัน)
    เทียบชื่อคอลัมน์แบบไม่สนตัวพิมพ์เล็ก/ใหญ่ และช่องว่างหน้า-หลัง (กัน Excel ใส่ช่องว่างเกินมาโดยไม่รู้ตัว)
    และจัดการค่าว่าง/NaN ให้ปลอดภัย ไม่ทำให้การนำเข้าพัง"""
    normalized = {str(k).strip().lower(): k for k in row.index}
    for n in names:
        actual_key = normalized.get(n.strip().lower())
        if actual_key is not None and pd.notna(row[actual_key]):
            val = str(row[actual_key]).strip()
            if val:
                return val
    return default

def _detect_col(columns, *names) -> Optional[str]:
    """เช็คว่าไฟล์ที่อัปโหลดมามีคอลัมน์ชื่อไหนตรงกับที่รองรับบ้าง (ไม่สนตัวพิมพ์เล็ก/ใหญ่และช่องว่าง)
    คืนชื่อคอลัมน์จริงในไฟล์ที่ตรงกัน หรือ None ถ้าไม่พบเลย — ใช้ทำสรุปแจ้งผู้ใช้หลังอัปโหลดว่าไฟล์มีคอลัมน์ที่ต้องการครบไหม"""
    normalized = {str(c).strip().lower(): c for c in columns}
    for n in names:
        found = normalized.get(n.strip().lower())
        if found is not None:
            return str(found)
    return None

def _normalize_room_type(raw: Optional[str]) -> str:
    """แปลงค่า room_type ที่ผู้ใช้พิมพ์มา (อาจสะกด/พิมพ์ไม่ตรงเป๊ะ เช่น "ห้องประจำ" แทน "ห้องประจำชั้น")
    ให้เป็นค่ามาตรฐาน 2 แบบเท่านั้น: "ห้องประจำชั้น" หรือ "ห้องปฏิบัติการ" — กันปัญหาจับคู่/แสดงผลพังเพราะสตริงไม่ตรงเป๊ะ"""
    if raw and "ประจำ" in raw:
        return "ห้องประจำชั้น"
    return "ห้องปฏิบัติการ"

def _check_schedule_conflicts(day_of_week: int, period_number: int, teacher_ids: List[str], classroom_ids: List[str], room_id: Optional[str], exclude_entry_id: Optional[str] = None, year_key: Optional[str] = None) -> List[str]:
    """ตรวจสอบครูสอนซ้ำ / ชั้นเรียนซ้ำ / ห้องซ้ำ / ครูติดล็อกเวลา / ติดกิจกรรมส่วนรวม ในคาบเดียวกัน (เฉพาะปี/เทอมเดียวกัน)"""
    conflicts: List[str] = []
    teacher_ids_set = set(teacher_ids)
    classroom_ids_set = set(classroom_ids)

    existing_docs = db.collection("schedule_entries") \
        .where("day_of_week", "==", day_of_week) \
        .where("period_number", "==", period_number).stream()
    for doc in existing_docs:
        if exclude_entry_id and doc.id == exclude_entry_id:
            continue
        data = doc.to_dict()
        if year_key and data.get("year_key") != year_key:
            continue
        if teacher_ids_set & set(data.get("teacher_ids", [])):
            conflicts.append("มีครูอย่างน้อย 1 ท่านสอนคาบนี้อยู่แล้ว")
        if classroom_ids_set & set(data.get("classroom_ids", [])):
            conflicts.append("มีชั้นเรียนอย่างน้อย 1 ห้องเรียนวิชาอื่นอยู่ในคาบนี้แล้ว")
        if room_id and data.get("room_id") == room_id:
            conflicts.append("สถานที่/ห้องนี้ถูกใช้งานในคาบนี้แล้ว")

    unavail_docs = db.collection("teacher_unavailabilities") \
        .where("day_of_week", "==", day_of_week) \
        .where("period_number", "==", period_number).stream()
    unavail_teacher_ids = {d.to_dict().get("teacher_id") for d in unavail_docs if not year_key or d.to_dict().get("year_key") == year_key}
    if teacher_ids_set & unavail_teacher_ids:
        conflicts.append("มีครูติดล็อกเวลาไม่ว่าง (unavailability) ในคาบนี้")

    event_docs = db.collection("fixed_events") \
        .where("day_of_week", "==", day_of_week) \
        .where("period_number", "==", period_number).stream()
    for ev in event_docs:
        if year_key and ev.to_dict().get("year_key") != year_key:
            continue
        ev_name = ev.to_dict().get("event_name", "กิจกรรม")
        parts = db.collection("event_participants").where("event_id", "==", ev.id).stream()
        for p in parts:
            pdata = p.to_dict()
            if pdata.get("participant_type") == "teacher" and pdata.get("participant_id") in teacher_ids_set:
                conflicts.append(f"ครูติดกิจกรรม '{ev_name}' ในคาบนี้")
            if pdata.get("participant_type") == "classroom" and pdata.get("participant_id") in classroom_ids_set:
                conflicts.append(f"ชั้นเรียนติดกิจกรรม '{ev_name}' ในคาบนี้")

    return conflicts

# Pydantic Models for API
class Teacher(BaseModel):
    id: Optional[str] = None
    full_name: str
    department: str
    teacher_code: Optional[str] = None

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
    # เฉพาะ room_type == "ห้องประจำชั้น": ผูกว่าห้องนี้คือห้องประจำของชั้นเรียนไหน (classroom_id)
    home_classroom_id: Optional[str] = None

class UnavailabilityCreate(BaseModel):
    teacher_ids: List[str]
    day_of_week: int
    period_number: int
    reason: Optional[str] = "ไม่ว่าง"

class UnavailabilityUpdate(BaseModel):
    teacher_id: str
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
    # รายชื่อ "ห้องปฏิบัติการ" ที่ครูวิชานี้สอนได้ (เลือกได้หลายห้อง) — ตอนจัดตารางอัตโนมัติ ระบบจะเลือกห้องที่ว่างจากรายการนี้ให้เอง
    # ถ้าปล่อยว่าง = สอนที่ห้องเรียนประจำของนักเรียนเอง ไม่ต้องจองห้องแยก
    room_ids: List[str] = []
    is_scout: Optional[bool] = False

class FixedEventCreate(BaseModel):
    event_name: str
    day_of_week: int
    period_number: int
    classroom_ids: List[str]
    teacher_ids: Optional[List[str]] = []
    room_id: Optional[str] = None

class ScheduleEntryCreate(BaseModel):
    # teacher_ids และ classroom_ids อนุญาตให้ว่างได้ฝั่งใดฝั่งหนึ่ง (แต่ไม่ใช่ทั้งคู่)
    # ใช้สำหรับกรณี "ชุมนุม (อิสระ)" ที่ฝั่งห้องเรียนกับฝั่งครูไม่ผูกกัน — ดูการตรวจสอบใน create_schedule_entry
    term_id: Optional[str] = None
    day_of_week: int
    period_number: int
    subject_id: str
    teacher_ids: List[str] = []
    classroom_ids: List[str] = []
    room_id: Optional[str] = None
    assignment_id: Optional[str] = None
    note: Optional[str] = None

class RoleUpdate(BaseModel):
    role: str

class AcademicYearCreate(BaseModel):
    year: str            # เช่น "2569"
    term: int            # 1 หรือ 2
    label: Optional[str] = None

class AcademicYearLabelUpdate(BaseModel):
    label: str

class SchoolInfoUpdate(BaseModel):
    school_name: Optional[str] = None
    logo_base64: Optional[str] = None

class DuplicateFromRequest(BaseModel):
    source_year_key: str
    copy_teachers: bool = True
    copy_subjects: bool = True
    copy_classrooms: bool = True
    copy_rooms: bool = True
    copy_department_priority: bool = True

# --- Academic Year / School Settings APIs ---
# ทุก collection ข้อมูล (ครู/วิชา/ห้องเรียน/ห้อง/ภาระงาน/ตารางสอน/ล็อกเวลา/กิจกรรม/ลำดับความสำคัญ)
# จะถูกผูกไว้กับ "year_key" (รูปแบบ "{ปีการศึกษา}_{เทอม}" เช่น "2569_1") เพื่อแยกข้อมูลรายปี/เทอมออกจากกันโดยสมบูรณ์
# Frontend จะแนบ year_key มากับทุก request ผ่าน axios interceptor โดยอัตโนมัติ

@app.get("/academic-years/")
async def list_academic_years():
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        docs = db.collection("academic_years").stream()
        years = [{"id": d.id, **d.to_dict()} for d in docs]
        years.sort(key=lambda y: (y.get("year", ""), y.get("term", 0)), reverse=True)
        return years
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/academic-years/")
async def create_academic_year(data: AcademicYearCreate, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    if data.term not in (1, 2):
        raise HTTPException(status_code=400, detail="เทอมต้องเป็น 1 หรือ 2 เท่านั้น")
    year_key = f"{data.year}_{data.term}"
    existing = list(db.collection("academic_years").where("year_key", "==", year_key).limit(1).stream())
    if existing:
        raise HTTPException(status_code=409, detail="ปีการศึกษา/เทอมนี้มีอยู่แล้ว")
    try:
        label = data.label or f"ปีการศึกษา {data.year} เทอม {data.term}"
        doc_data = {"year": data.year, "term": data.term, "year_key": year_key, "label": label}
        _, doc_ref = db.collection("academic_years").add(doc_data)
        return {"status": "success", "id": doc_ref.id, "year_key": year_key}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.put("/academic-years/{doc_id}")
async def update_academic_year_label(doc_id: str, data: AcademicYearLabelUpdate, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    if not data.label.strip():
        raise HTTPException(status_code=400, detail="กรุณากรอกชื่อปีการศึกษา")
    try:
        db.collection("academic_years").document(doc_id).update({"label": data.label.strip()})
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/academic-years/{doc_id}")
async def delete_academic_year(doc_id: str, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("academic_years").document(doc_id).delete()
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/academic-years/{target_year_key}/duplicate")
async def duplicate_academic_year_data(target_year_key: str, data: DuplicateFromRequest, admin: dict = Depends(require_admin)):
    """คัดลอกข้อมูลพื้นฐาน (ครู/วิชา/ห้องเรียน/ห้อง/ลำดับความสำคัญกลุ่มสาระ) จากปี/เทอมก่อนหน้า มาไว้ในปี/เทอมใหม่"""
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        result = {}
        mapping = [
            ("teachers", data.copy_teachers, {"id"}),
            ("subjects", data.copy_subjects, {"id"}),
            ("classrooms", data.copy_classrooms, {"id"}),
            ("rooms", data.copy_rooms, {"id"}),
        ]
        for coll_name, should_copy, exclude_fields in mapping:
            if not should_copy:
                continue
            count = 0
            src_docs = db.collection(coll_name).where("year_key", "==", data.source_year_key).stream()
            for doc in src_docs:
                d = doc.to_dict()
                for f in exclude_fields:
                    d.pop(f, None)
                d["year_key"] = target_year_key
                db.collection(coll_name).add(d)
                count += 1
            result[coll_name] = count

        if data.copy_department_priority:
            src_pref = db.collection("settings").document(f"department_priority_{data.source_year_key}").get()
            if src_pref.exists:
                order = src_pref.to_dict().get("order", [])
                db.collection("settings").document(f"department_priority_{target_year_key}").set({"order": order})
                result["department_priority"] = len(order)

        return {"status": "success", "copied": result}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/settings/school-info")
async def get_school_info():
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        doc = db.collection("settings").document("school_info").get()
        return doc.to_dict() if doc.exists else {"school_name": None, "logo_base64": None}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.put("/settings/school-info")
async def set_school_info(data: SchoolInfoUpdate, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("settings").document("school_info").set(data.model_dump(exclude_none=True), merge=True)
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- GET APIs (ดึงข้อมูลมาแสดงที่ Frontend) ---

@app.get("/fixed-events/")
async def get_fixed_events(year_key: Optional[str] = None):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        # ดึง Lookup tables
        classrooms_map = {doc.id: f"{doc.to_dict().get('grade_level')}/{doc.to_dict().get('room_name')}" for doc in db.collection("classrooms").stream()}
        teachers_map = {doc.id: doc.to_dict().get("full_name") for doc in db.collection("teachers").stream()}
        rooms_map = {doc.id: doc.to_dict().get("room_name") for doc in db.collection("rooms").stream()}

        events = []
        event_docs = db.collection("fixed_events").where("year_key", "==", year_key).stream() if year_key else db.collection("fixed_events").stream()
        for doc in event_docs:
            data = doc.to_dict()
            e_id = doc.id
            
            # ดึงผู้เข้าร่วม (ทั้งชื่อสำหรับแสดงผล และ id ไว้ prefill ตอนกด "แก้ไข")
            c_names, t_names, c_ids, t_ids = [], [], [], []
            part_docs = db.collection("event_participants").where("event_id", "==", e_id).stream()
            for p in part_docs:
                p_data = p.to_dict()
                p_id = p_data.get("participant_id")
                if p_data.get("participant_type") == "classroom":
                    c_ids.append(p_id)
                    if p_id in classrooms_map: c_names.append(classrooms_map[p_id])
                elif p_data.get("participant_type") == "teacher":
                    t_ids.append(p_id)
                    if p_id in teachers_map: t_names.append(teachers_map[p_id])

            # เรียงชื่อห้องเรียน/ครูให้ดูง่าย (ม.1/1 -> ม.1/12 แบบ natural sort, ชื่อครูเรียงตามตัวอักษร)
            c_names.sort(key=_natural_key)
            t_names.sort(key=_natural_key)

            events.append({
                "id": e_id,
                "event_name": data.get("event_name"),
                "day_of_week": data.get("day_of_week"),
                "period_number": data.get("period_number"),
                "classroom_names": c_names,
                "teacher_names": t_names,
                "classroom_ids": c_ids,
                "teacher_ids": t_ids,
                "room_id": data.get("room_id"),
                "room_name": rooms_map.get(data.get("room_id"), "ไม่ระบุ")
            })
        # เรียงรายการกิจกรรมตามวัน (จันทร์->ศุกร์) แล้วตามคาบที่
        events.sort(key=lambda ev: (ev.get("day_of_week") or 0, ev.get("period_number") or 0))
        return events
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/fixed-events/")
async def create_fixed_event(data: FixedEventCreate, year_key: Optional[str] = None, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        event_data = {
            "event_name": data.event_name,
            "day_of_week": data.day_of_week,
            "period_number": data.period_number,
            "room_id": data.room_id,
            "year_key": year_key,
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

@app.put("/fixed-events/{event_id}")
async def update_fixed_event(event_id: str, data: FixedEventCreate, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("fixed_events").document(event_id).update({
            "event_name": data.event_name,
            "day_of_week": data.day_of_week,
            "period_number": data.period_number,
            "room_id": data.room_id,
        })
        # ลบผู้เข้าร่วมเดิมแล้วสร้างใหม่ทั้งหมด (ง่ายและชัวร์กว่าการ diff รายการ)
        for p in db.collection("event_participants").where("event_id", "==", event_id).stream():
            p.reference.delete()
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
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/fixed-events/{event_id}")
async def delete_fixed_event(event_id: str, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("fixed_events").document(event_id).delete()
        parts = db.collection("event_participants").where("event_id", "==", event_id).stream()
        for p in parts: p.reference.delete()
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.get("/assignments/")
async def get_assignments(year_key: Optional[str] = None):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        teachers_map = {doc.id: doc.to_dict().get("full_name") for doc in db.collection("teachers").stream()}
        subjects_map = {doc.id: f"{doc.to_dict().get('subject_code')} {doc.to_dict().get('subject_name')}" for doc in db.collection("subjects").stream()}
        classrooms_map = {doc.id: f"{doc.to_dict().get('grade_level')}/{doc.to_dict().get('room_name')}" for doc in db.collection("classrooms").stream()}
        rooms_map = {doc.id: doc.to_dict().get("room_name") for doc in db.collection("rooms").stream()}

        assignments = []
        assign_docs = db.collection("assignments").where("year_key", "==", year_key).stream() if year_key else db.collection("assignments").stream()
        for doc in assign_docs:
            data = doc.to_dict()
            a_id = doc.id
            t_names, t_ids = [], []
            t_rels = db.collection("assignment_teachers").where("assignment_id", "==", a_id).stream()
            for rel in t_rels:
                t_id = rel.to_dict().get("teacher_id")
                t_ids.append(t_id)
                if t_id in teachers_map: t_names.append(teachers_map[t_id])
            c_names, c_ids = [], []
            c_rels = db.collection("assignment_classrooms").where("assignment_id", "==", a_id).stream()
            for rel in c_rels:
                c_id = rel.to_dict().get("classroom_id")
                c_ids.append(c_id)
                if c_id in classrooms_map: c_names.append(classrooms_map[c_id])
            # room_ids = ห้องปฏิบัติการที่เลือกไว้ (เลือกได้หลายห้อง). รองรับข้อมูลเก่าที่เคยเก็บเป็น room_id เดี่ยว
            room_ids = data.get("room_ids")
            if room_ids is None:
                room_ids = [data["room_id"]] if data.get("room_id") else []
            room_names = [rooms_map[r] for r in room_ids if r in rooms_map]
            assignments.append({
                "id": a_id,
                "subject_id": data.get("subject_id"),
                "subject_name": subjects_map.get(data.get("subject_id"), "ไม่ทราบวิชา"),
                "teacher_names": t_names,
                "teacher_ids": t_ids,
                "classroom_names": c_names,
                "classroom_ids": c_ids,
                "room_ids": room_ids,
                "room_names": room_names,
                "total_periods": data.get("total_periods"),
                "period_split": data.get("period_split"),
                "is_scout": data.get("is_scout", False)
            })
        return assignments
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/assignments/")
async def create_assignment(data: AssignmentCreate, year_key: Optional[str] = None, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        assignment_data = {
            "subject_id": data.subject_id,
            "total_periods": data.total_periods,
            "period_split": data.period_split,
            "term_id": data.term_id,
            "room_ids": data.room_ids or [],
            "is_scout": data.is_scout or False,
            "year_key": year_key,
        }
        _, doc_ref = db.collection("assignments").add(assignment_data)
        assignment_id = doc_ref.id
        for t_id in data.teacher_ids:
            db.collection("assignment_teachers").add({"assignment_id": assignment_id, "teacher_id": t_id})
        for c_id in data.classroom_ids:
            db.collection("assignment_classrooms").add({"assignment_id": assignment_id, "classroom_id": c_id})
        return {"status": "success", "assignment_id": assignment_id}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.put("/assignments/{assignment_id}")
async def update_assignment(assignment_id: str, data: AssignmentCreate, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("assignments").document(assignment_id).update({
            "subject_id": data.subject_id,
            "total_periods": data.total_periods,
            "period_split": data.period_split,
            "room_ids": data.room_ids or [],
            "room_id": firestore.DELETE_FIELD,  # เคลียร์ฟิลด์เก่าแบบเดี่ยวทิ้ง (ถ้ามี) หลังแก้ไขแล้วให้ใช้ room_ids เท่านั้น
            "is_scout": data.is_scout or False,
        })
        # ลบความสัมพันธ์เดิมแล้วสร้างใหม่ทั้งหมด
        for rel in db.collection("assignment_teachers").where("assignment_id", "==", assignment_id).stream():
            rel.reference.delete()
        for rel in db.collection("assignment_classrooms").where("assignment_id", "==", assignment_id).stream():
            rel.reference.delete()
        for t_id in data.teacher_ids:
            db.collection("assignment_teachers").add({"assignment_id": assignment_id, "teacher_id": t_id})
        for c_id in data.classroom_ids:
            db.collection("assignment_classrooms").add({"assignment_id": assignment_id, "classroom_id": c_id})
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/assignments/{assignment_id}")
async def delete_assignment(assignment_id: str, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("assignments").document(assignment_id).delete()
        for rel in db.collection("assignment_teachers").where("assignment_id", "==", assignment_id).stream():
            rel.reference.delete()
        for rel in db.collection("assignment_classrooms").where("assignment_id", "==", assignment_id).stream():
            rel.reference.delete()
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- Teacher Unavailability APIs ---

@app.get("/unavailabilities/")
async def get_all_unavailabilities(year_key: Optional[str] = None):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        teachers_map = {doc.id: doc.to_dict().get("full_name") for doc in db.collection("teachers").stream()}
        docs = db.collection("teacher_unavailabilities").where("year_key", "==", year_key).stream() if year_key else db.collection("teacher_unavailabilities").stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            t_id = data.get("teacher_id")
            results.append({
                "id": doc.id,
                "teacher_id": t_id,
                "teacher_name": teachers_map.get(t_id, "ไม่ทราบชื่อ"),
                "day_of_week": data.get("day_of_week"),
                "period_number": data.get("period_number"),
                "reason": data.get("reason")
            })
        return results
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/unavailabilities/")
async def create_unavailabilities(data: UnavailabilityCreate, year_key: Optional[str] = None, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        for t_id in data.teacher_ids:
            db.collection("teacher_unavailabilities").add({
                "teacher_id": t_id,
                "day_of_week": data.day_of_week,
                "period_number": data.period_number,
                "reason": data.reason,
                "year_key": year_key,
            })
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.put("/unavailabilities/{doc_id}")
async def update_unavailability(doc_id: str, data: UnavailabilityUpdate, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("teacher_unavailabilities").document(doc_id).update({
            "teacher_id": data.teacher_id,
            "day_of_week": data.day_of_week,
            "period_number": data.period_number,
            "reason": data.reason,
        })
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/unavailabilities/{doc_id}")
async def delete_unavailability(doc_id: str, user: dict = Depends(get_current_user)):
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
async def get_teachers(year_key: Optional[str] = None):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    docs = db.collection("teachers").where("year_key", "==", year_key).stream() if year_key else db.collection("teachers").stream()
    result = [{"id": doc.id, **{k: v for k, v in doc.to_dict().items() if k in ("full_name", "department", "teacher_code")}} for doc in docs]
    # เรียงตามรหัส ID ก่อน (ถ้ามี) ไม่มีรหัสให้ไปอยู่ท้ายสุด เรียงตามชื่อแทน
    result.sort(key=lambda t: (0, _natural_key(t.get("teacher_code"))) if t.get("teacher_code") else (1, _natural_key(t.get("full_name"))))
    return result

@app.get("/subjects/", response_model=List[Subject])
async def get_subjects(year_key: Optional[str] = None):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    docs = db.collection("subjects").where("year_key", "==", year_key).stream() if year_key else db.collection("subjects").stream()
    result = [{"id": doc.id, **{k: v for k, v in doc.to_dict().items() if k in ("subject_code", "subject_name")}} for doc in docs]
    result.sort(key=lambda s: _natural_key(s.get("subject_code")))
    return result

@app.get("/classrooms/", response_model=List[Classroom])
async def get_classrooms(year_key: Optional[str] = None):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    docs = db.collection("classrooms").where("year_key", "==", year_key).stream() if year_key else db.collection("classrooms").stream()
    result = [{"id": doc.id, **{k: v for k, v in doc.to_dict().items() if k in ("grade_level", "room_name", "lunch_period")}} for doc in docs]
    # เรียงตามระดับชั้นก่อน (ม.1 -> ม.6) แล้วค่อยเรียงตามห้อง (1/1 -> 1/12) แบบ natural sort
    result.sort(key=lambda c: (_natural_key(c.get("grade_level")), _natural_key(c.get("room_name"))))
    return result

@app.get("/rooms/")
async def get_rooms(year_key: Optional[str] = None):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    docs = db.collection("rooms").where("year_key", "==", year_key).stream() if year_key else db.collection("rooms").stream()
    classrooms_map = {
        d.id: f"{d.to_dict().get('grade_level')}/{d.to_dict().get('room_name')}"
        for d in (db.collection("classrooms").where("year_key", "==", year_key).stream() if year_key else db.collection("classrooms").stream())
    }
    result = []
    for doc in docs:
        data = doc.to_dict()
        home_classroom_id = data.get("home_classroom_id")
        result.append({
            "id": doc.id,
            "room_name": data.get("room_name"),
            "room_type": data.get("room_type"),
            "home_classroom_id": home_classroom_id,
            "home_classroom_label": classrooms_map.get(home_classroom_id) if home_classroom_id else None,
        })
    result.sort(key=lambda r: _natural_key(r.get("room_name")))
    return result

@app.post("/classrooms/manual")
async def create_classroom_manual(data: Classroom, year_key: Optional[str] = None, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("classrooms").add({**data.model_dump(exclude={"id"}), "year_key": year_key})
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/rooms/manual")
async def create_room_manual(data: Room, year_key: Optional[str] = None, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        room_data = data.model_dump(exclude={"id"})
        room_data["room_type"] = _normalize_room_type(room_data.get("room_type"))
        db.collection("rooms").add({**room_data, "year_key": year_key})
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/subjects/manual")
async def create_subject_manual(data: Subject, year_key: Optional[str] = None, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("subjects").add({**data.model_dump(exclude={"id"}), "year_key": year_key})
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/teachers/manual")
async def create_teacher_manual(data: Teacher, year_key: Optional[str] = None, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("teachers").add({**data.model_dump(exclude={"id"}), "year_key": year_key})
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- Delete APIs สำหรับข้อมูลพื้นฐาน (ลบทีละรายการ หรือล้างทั้งหมดก่อนอัปโหลดใหม่) ---
# หมายเหตุ: การอัปโหลด CSV/Excel เป็นการ "เพิ่ม" ข้อมูลต่อท้ายเสมอ ไม่ทับของเดิม
# ถ้าต้องการอัปโหลดใหม่ทับของเก่า ให้กดล้างข้อมูลก่อน แล้วค่อยอัปโหลดไฟล์ใหม่

def _clear_collection(collection_name: str, year_key: Optional[str]) -> int:
    if not year_key:
        raise HTTPException(status_code=400, detail="ต้องเลือกปีการศึกษาก่อนจึงจะล้างข้อมูลได้ (เพื่อป้องกันการลบข้อมูลปีอื่นโดยไม่ตั้งใจ)")
    deleted = 0
    # กวาดล้างทั้งข้อมูลของปีที่เลือกอยู่ และข้อมูลเก่าที่ยังไม่มี year_key
    # (เช่น ข้อมูลที่อัปโหลดไว้ตั้งแต่ก่อนมีระบบปีการศึกษา) เพื่อไม่ให้ตกค้างแบบลบไม่ได้
    for doc in db.collection(collection_name).stream():
        doc_year_key = doc.to_dict().get("year_key")
        if doc_year_key == year_key or not doc_year_key:
            doc.reference.delete()
            deleted += 1
    return deleted

@app.delete("/teachers/{teacher_id}")
async def delete_teacher(teacher_id: str, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("teachers").document(teacher_id).delete()
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/teachers/")
async def clear_teachers(year_key: Optional[str] = None, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        return {"status": "success", "deleted_count": _clear_collection("teachers", year_key)}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/subjects/{subject_id}")
async def delete_subject(subject_id: str, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("subjects").document(subject_id).delete()
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/subjects/")
async def clear_subjects(year_key: Optional[str] = None, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        return {"status": "success", "deleted_count": _clear_collection("subjects", year_key)}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/classrooms/{classroom_id}")
async def delete_classroom(classroom_id: str, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("classrooms").document(classroom_id).delete()
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/classrooms/")
async def clear_classrooms(year_key: Optional[str] = None, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        return {"status": "success", "deleted_count": _clear_collection("classrooms", year_key)}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/rooms/{room_id}")
async def delete_room(room_id: str, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("rooms").document(room_id).delete()
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/rooms/")
async def clear_rooms(year_key: Optional[str] = None, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        return {"status": "success", "deleted_count": _clear_collection("rooms", year_key)}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- Update (แก้ไข) APIs สำหรับข้อมูลพื้นฐาน ---

@app.put("/teachers/{teacher_id}")
async def update_teacher(teacher_id: str, data: Teacher, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("teachers").document(teacher_id).update(data.model_dump(exclude={"id"}, exclude_none=True))
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.put("/subjects/{subject_id}")
async def update_subject(subject_id: str, data: Subject, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("subjects").document(subject_id).update(data.model_dump(exclude={"id"}, exclude_none=True))
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.put("/classrooms/{classroom_id}")
async def update_classroom(classroom_id: str, data: Classroom, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("classrooms").document(classroom_id).update(data.model_dump(exclude={"id"}, exclude_none=True))
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.put("/rooms/{room_id}")
async def update_room(room_id: str, data: Room, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        update_data = data.model_dump(exclude={"id"}, exclude_none=True)
        # กันค่า room_type ที่พิมพ์มาไม่ตรงเป๊ะ (เช่น "ห้องประจำ" แทน "ห้องประจำชั้น") ให้กลายเป็นค่ามาตรฐานเสมอ
        if "room_type" in update_data:
            update_data["room_type"] = _normalize_room_type(update_data["room_type"])
        # อนุญาตให้เคลียร์ home_classroom_id เป็นค่าว่างได้เสมอ (เช่น เปลี่ยนประเภทห้องจาก "ห้องประจำชั้น" เป็น "ห้องปฏิบัติการ")
        update_data["home_classroom_id"] = data.home_classroom_id
        db.collection("rooms").document(room_id).update(update_data)
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- Auth / Users APIs ---

@app.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user

@app.get("/users/")
async def list_users(admin: dict = Depends(require_admin)):
    docs = db.collection("users").stream()
    return [{"uid": d.id, **d.to_dict()} for d in docs]

@app.patch("/users/{uid}/role")
async def update_user_role(uid: str, data: RoleUpdate, admin: dict = Depends(require_admin)):
    if data.role not in ("admin", "teacher"):
        raise HTTPException(status_code=400, detail="role ต้องเป็น admin หรือ teacher")
    db.collection("users").document(uid).update({"role": data.role})
    return {"status": "success"}

# --- Manual Schedule (จัดตารางสอนแบบ manual ทีละคาบ) ---

@app.get("/schedule/")
async def get_schedule_entries(classroom_id: Optional[str] = None, teacher_id: Optional[str] = None, term_id: Optional[str] = None, year_key: Optional[str] = None):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        subjects_map = {doc.id: f"{doc.to_dict().get('subject_code')} {doc.to_dict().get('subject_name')}" for doc in db.collection("subjects").stream()}
        teachers_map = {doc.id: doc.to_dict().get("full_name") for doc in db.collection("teachers").stream()}
        classrooms_map = {doc.id: f"{doc.to_dict().get('grade_level')}/{doc.to_dict().get('room_name')}" for doc in db.collection("classrooms").stream()}
        rooms_map = {}
        home_room_by_classroom = {}  # classroom_id -> ชื่อห้องประจำชั้น (ถ้าผูกไว้)
        for doc in db.collection("rooms").stream():
            r_data = doc.to_dict()
            rooms_map[doc.id] = r_data.get("room_name")
            home_cid = r_data.get("home_classroom_id")
            if home_cid:
                home_room_by_classroom[home_cid] = r_data.get("room_name")

        results = []
        for doc in db.collection("schedule_entries").stream():
            data = doc.to_dict()
            if year_key and data.get("year_key") != year_key: continue
            if classroom_id and classroom_id not in data.get("classroom_ids", []): continue
            if teacher_id and teacher_id not in data.get("teacher_ids", []): continue
            if term_id and data.get("term_id") != term_id: continue
            entry_classroom_ids = data.get("classroom_ids", [])
            explicit_room_id = data.get("room_id")
            # ถ้าไม่ได้จองห้องปฏิบัติการไว้ ให้ลองเอา "ห้องประจำชั้น" ของห้องเรียนนั้นมาแสดงแทน (ถ้ามีการผูกไว้)
            fallback_room_name = None
            if not explicit_room_id:
                for c in entry_classroom_ids:
                    if c in home_room_by_classroom:
                        fallback_room_name = home_room_by_classroom[c]
                        break
            results.append({
                "id": doc.id,
                "day_of_week": data.get("day_of_week"),
                "period_number": data.get("period_number"),
                "subject_id": data.get("subject_id"),
                "subject_name": subjects_map.get(data.get("subject_id"), "ไม่ทราบวิชา"),
                "teacher_ids": data.get("teacher_ids", []),
                "teacher_names": [teachers_map.get(t, "ไม่ทราบชื่อ") for t in data.get("teacher_ids", [])],
                "classroom_ids": entry_classroom_ids,
                "classroom_names": [classrooms_map.get(c, "ไม่ทราบห้อง") for c in entry_classroom_ids],
                "room_id": explicit_room_id,
                "room_name": rooms_map.get(explicit_room_id) if explicit_room_id else fallback_room_name,
                "note": data.get("note"),
                "created_by_name": data.get("created_by_name"),
                "source": data.get("source", "manual"),
            })
        return results
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/schedule/")
async def create_schedule_entry(data: ScheduleEntryCreate, year_key: Optional[str] = None, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    # ต้องระบุอย่างน้อยฝั่งใดฝั่งหนึ่ง (ครู หรือ ชั้นเรียน) — รองรับกรณี "ชุมนุม (อิสระ)" ที่บันทึกฝั่งห้องเรียน
    # กับฝั่งครูแยกจากกัน โดยไม่ต้องผูกกัน
    if not data.teacher_ids and not data.classroom_ids:
        raise HTTPException(status_code=400, detail="ต้องระบุครูผู้สอนหรือชั้นเรียนอย่างน้อยหนึ่งอย่าง")
    conflicts = _check_schedule_conflicts(data.day_of_week, data.period_number, data.teacher_ids, data.classroom_ids, data.room_id, year_key=year_key)
    if conflicts:
        raise HTTPException(status_code=409, detail={"message": "พบตารางซ้ำซ้อนในคาบนี้", "conflicts": conflicts})
    try:
        entry_data = data.model_dump()
        entry_data["created_by"] = user["uid"]
        entry_data["created_by_name"] = user.get("name") or user.get("email")
        entry_data["source"] = "manual"
        entry_data["year_key"] = year_key
        _, doc_ref = db.collection("schedule_entries").add(entry_data)
        return {"status": "success", "id": doc_ref.id}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/schedule/{entry_id}")
async def delete_schedule_entry(entry_id: str, user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        db.collection("schedule_entries").document(entry_id).delete()
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.delete("/schedule/auto")
async def clear_auto_schedule(term_id: Optional[str] = None, year_key: Optional[str] = None, admin: dict = Depends(require_admin)):
    """ลบเฉพาะตารางที่ระบบ Auto Solver จัดไว้ (source == 'auto') ไม่แตะตารางที่ admin/ครูจัดด้วยมือ (เฉพาะปี/เทอมปัจจุบัน)"""
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        deleted = 0
        for doc in db.collection("schedule_entries").where("source", "==", "auto").stream():
            d = doc.to_dict()
            if year_key and d.get("year_key") != year_key:
                continue
            if term_id and d.get("term_id") and d.get("term_id") != term_id:
                continue
            doc.reference.delete()
            deleted += 1
        return {"status": "success", "deleted_count": deleted}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- Settings: ลำดับความสำคัญกลุ่มสาระ (ใช้ตอนจัดตารางอัตโนมัติ) — แยกตามปี/เทอม ---

class DepartmentPriorityUpdate(BaseModel):
    order: List[str]

@app.get("/settings/department-priority")
async def get_department_priority(year_key: Optional[str] = None):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        doc_id = f"department_priority_{year_key}" if year_key else "department_priority"
        doc = db.collection("settings").document(doc_id).get()
        order = doc.to_dict().get("order", []) if doc.exists else []
        # เติมกลุ่มสาระที่มีครูอยู่จริงแต่ยังไม่เคยจัดลำดับ ต่อท้ายให้ครบอัตโนมัติ (เฉพาะปี/เทอมปัจจุบัน)
        teacher_docs = db.collection("teachers").where("year_key", "==", year_key).stream() if year_key else db.collection("teachers").stream()
        all_depts = sorted({d.to_dict().get("department") for d in teacher_docs if d.to_dict().get("department")})
        for dept in all_depts:
            if dept not in order:
                order.append(dept)
        return {"order": order}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.put("/settings/department-priority")
async def set_department_priority(data: DepartmentPriorityUpdate, year_key: Optional[str] = None, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        doc_id = f"department_priority_{year_key}" if year_key else "department_priority"
        db.collection("settings").document(doc_id).set({"order": data.order})
        return {"status": "success"}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

# --- Flow 3: Auto Solver (จัดตารางสอนอัตโนมัติ) ---
# ทำงานเป็นเฟสตามลำดับที่ออกแบบไว้ (ดู flow การทำงาน.txt):
#   เฟส 0 (ทำอยู่แล้วผ่าน _slot_is_free): บล็อคคาบที่ล็อคไว้ (fixed_events / teacher_unavailabilities / lunch_period)
#         และคาบที่มีอยู่แล้วใน schedule_entries (ทั้งที่ admin จัดมือ และที่ auto จัดไปแล้วในรอบก่อนหน้า)
#   เฟส 1: คาบคู่ ครูเดี่ยว เรียงตามลำดับกลุ่มสาระที่ตั้งไว้ใน settings/department_priority
#   เฟส 2: ครูสอนร่วม (มากกว่า 1 คน) — ลูกเสือ/เนตรนารี/ยุวกาชาดก่อน -> คาบคู่สอนร่วม -> คาบเดี่ยวสอนร่วม
#   เฟส 3: คาบเดี่ยว ครูเดี่ยวที่เหลือทั้งหมด
# กฎร่วมทุกเฟส (hard): ครู/ชั้นเรียน/ห้อง ห้ามชนกัน, วิชาคาบเดี่ยวห้ามซ้ำวันเดียวกันในห้องเดียวกัน
# กฎร่วม (soft): พยายามไม่ให้ครูสอนติดกันเกิน 2 คาบ ถ้าเลี่ยงไม่ได้จะจัดให้แต่ขึ้นเตือน
# รายการที่จัดไม่ลงจะถูกปล่อยว่างไว้ (ไม่ทำให้ทั้งรอบ fail) ให้ admin ไปจัดต่อเองผ่านหน้า "จัดตารางสอน Manual"

DAYS = [1, 2, 3, 4, 5]
PERIODS = list(range(1, 9))

def _load_solver_data(term_id: Optional[str], year_key: Optional[str] = None):
    teacher_docs = db.collection("teachers").where("year_key", "==", year_key).stream() if year_key else db.collection("teachers").stream()
    teachers = {d.id: d.to_dict() for d in teacher_docs}
    subject_docs = db.collection("subjects").where("year_key", "==", year_key).stream() if year_key else db.collection("subjects").stream()
    subjects = {d.id: d.to_dict() for d in subject_docs}
    classroom_docs = db.collection("classrooms").where("year_key", "==", year_key).stream() if year_key else db.collection("classrooms").stream()
    classrooms = {d.id: d.to_dict() for d in classroom_docs}

    assignments = []
    assignment_docs = db.collection("assignments").where("year_key", "==", year_key).stream() if year_key else db.collection("assignments").stream()
    for doc in assignment_docs:
        data = doc.to_dict()
        if term_id and data.get("term_id") and data.get("term_id") != term_id:
            continue
        a_id = doc.id
        t_ids = [r.to_dict().get("teacher_id") for r in db.collection("assignment_teachers").where("assignment_id", "==", a_id).stream()]
        c_ids = [r.to_dict().get("classroom_id") for r in db.collection("assignment_classrooms").where("assignment_id", "==", a_id).stream()]
        if not t_ids or not c_ids:
            continue
        # room_ids = รายการห้องปฏิบัติการที่เลือกไว้ (รองรับข้อมูลเก่าที่เคยเก็บเป็น room_id เดี่ยว)
        room_ids = data.get("room_ids")
        if room_ids is None:
            room_ids = [data["room_id"]] if data.get("room_id") else []
        assignments.append({
            "id": a_id,
            "subject_id": data.get("subject_id"),
            "teacher_ids": t_ids,
            "classroom_ids": c_ids,
            "room_ids": room_ids,
            "total_periods": data.get("total_periods", 1),
            "period_split": data.get("period_split") or [data.get("total_periods", 1)],
            "is_scout": bool(data.get("is_scout", False)),
            "term_id": data.get("term_id"),
        })
    return teachers, subjects, classrooms, assignments

def _blocked_from_fixed_and_unavailable(year_key: Optional[str] = None):
    """คืนคาบที่ถูกล็อคไว้ล่วงหน้า: (day,period,teacher_id) และ (day,period,classroom_id)"""
    blocked_teacher_slots = set()
    blocked_classroom_slots = set()

    unavail_docs = db.collection("teacher_unavailabilities").where("year_key", "==", year_key).stream() if year_key else db.collection("teacher_unavailabilities").stream()
    for doc in unavail_docs:
        d = doc.to_dict()
        blocked_teacher_slots.add((d.get("day_of_week"), d.get("period_number"), d.get("teacher_id")))

    fixed_event_docs = db.collection("fixed_events").where("year_key", "==", year_key).stream() if year_key else db.collection("fixed_events").stream()
    for ev in fixed_event_docs:
        ev_data = ev.to_dict()
        day, period = ev_data.get("day_of_week"), ev_data.get("period_number")
        for p in db.collection("event_participants").where("event_id", "==", ev.id).stream():
            pdata = p.to_dict()
            if pdata.get("participant_type") == "teacher":
                blocked_teacher_slots.add((day, period, pdata.get("participant_id")))
            elif pdata.get("participant_type") == "classroom":
                blocked_classroom_slots.add((day, period, pdata.get("participant_id")))

    return blocked_teacher_slots, blocked_classroom_slots

def _load_occupied(term_id: Optional[str], year_key: Optional[str] = None):
    """โหลดคาบที่ถูกจองไปแล้วใน schedule_entries (ทั้ง manual และ auto ของรอบก่อน) เป็นจุดตั้งต้น"""
    occupied = {}
    for doc in db.collection("schedule_entries").stream():
        d = doc.to_dict()
        if year_key and d.get("year_key") != year_key:
            continue
        if term_id and d.get("term_id") and d.get("term_id") != term_id:
            continue
        key = (d.get("day_of_week"), d.get("period_number"))
        slot = occupied.setdefault(key, {"teachers": set(), "classrooms": set(), "rooms": set(), "subj_by_class": {}})
        slot["teachers"].update(d.get("teacher_ids", []))
        slot["classrooms"].update(d.get("classroom_ids", []))
        if d.get("room_id"):
            slot["rooms"].add(d.get("room_id"))
        for c in d.get("classroom_ids", []):
            slot["subj_by_class"].setdefault(c, set()).add(d.get("subject_id"))
    return occupied

def _load_teacher_day_periods(term_id: Optional[str], year_key: Optional[str] = None):
    result = {}
    for doc in db.collection("schedule_entries").stream():
        d = doc.to_dict()
        if year_key and d.get("year_key") != year_key:
            continue
        if term_id and d.get("term_id") and d.get("term_id") != term_id:
            continue
        for t in d.get("teacher_ids", []):
            key = (t, d.get("day_of_week"))
            result.setdefault(key, []).append(d.get("period_number"))
    return result

def _would_exceed_consecutive(teacher_day_periods, teacher_id, day, period, limit=2):
    periods = sorted(teacher_day_periods.get((teacher_id, day), []) + [period])
    run = 1
    for i in range(1, len(periods)):
        if periods[i] == periods[i - 1] + 1:
            run += 1
            if run > limit:
                return True
        else:
            run = 1
    return False

def _subject_already_on_day(occupied, day, classroom_ids, subject_id):
    for (d, _p), slot in occupied.items():
        if d != day:
            continue
        for c in classroom_ids:
            if subject_id in slot.get("subj_by_class", {}).get(c, set()):
                return True
    return False

def _pick_available_room(occupied, day, period_range, room_ids):
    """เลือกห้องปฏิบัติการที่ว่างตลอดช่วงคาบที่กำหนด จากรายการที่ครูวิชานี้เลือกไว้
    คืนค่า: None = ไม่ต้องใช้ห้อง (สอนที่ห้องประจำของนักเรียนเอง, room_ids ว่าง),
            str = room_id ที่เลือกได้, False = ระบุห้องไว้แต่ไม่มีห้องไหนว่างเลยในช่วงนี้"""
    if not room_ids:
        return None
    for rid in room_ids:
        free = True
        for p in period_range:
            slot = occupied.get((day, p))
            if slot and rid in slot["rooms"]:
                free = False
                break
        if free:
            return rid
    return False

def _slot_is_free(occupied, blocked_teacher_slots, blocked_classroom_slots, classrooms, day, period_range, a):
    for p in period_range:
        for t in a["teacher_ids"]:
            if (day, p, t) in blocked_teacher_slots:
                return False
        for c in a["classroom_ids"]:
            if (day, p, c) in blocked_classroom_slots:
                return False
            lunch = classrooms.get(c, {}).get("lunch_period")
            if lunch and p == lunch:
                return False
        slot = occupied.get((day, p))
        if slot:
            if set(a["teacher_ids"]) & slot["teachers"]:
                return False
            if set(a["classroom_ids"]) & slot["classrooms"]:
                return False
    # เช็คว่ามีห้องปฏิบัติการว่างให้เลือกอย่างน้อย 1 ห้อง (ถ้าวิชานี้ระบุตัวเลือกห้องไว้)
    if a.get("room_ids") and _pick_available_room(occupied, day, period_range, a["room_ids"]) is False:
        return False
    return True

def _department_priority_order(year_key: Optional[str] = None):
    doc_id = f"department_priority_{year_key}" if year_key else "department_priority"
    doc = db.collection("settings").document(doc_id).get()
    return doc.to_dict().get("order", []) if doc.exists else []

def _dept_sort_key(dept, priority_order):
    return priority_order.index(dept) if dept in priority_order else len(priority_order)

def run_auto_solver(term_id: Optional[str] = None, year_key: Optional[str] = None):
    teachers, subjects, classrooms, assignments = _load_solver_data(term_id, year_key)
    priority_order = _department_priority_order(year_key)

    # เคลียร์ผลลัพธ์ auto รอบก่อนหน้าทิ้งก่อน (ไม่แตะของที่จัดด้วยมือ) แล้วค่อยจัดใหม่
    for doc in db.collection("schedule_entries").where("source", "==", "auto").stream():
        d = doc.to_dict()
        if year_key and d.get("year_key") != year_key:
            continue
        if term_id and d.get("term_id") and d.get("term_id") != term_id:
            continue
        doc.reference.delete()

    blocked_teacher_slots, blocked_classroom_slots = _blocked_from_fixed_and_unavailable(year_key)
    occupied = _load_occupied(term_id, year_key)
    teacher_day_periods = _load_teacher_day_periods(term_id, year_key)

    def is_double(a):
        return any(x >= 2 for x in a["period_split"])

    def is_coteach(a):
        return len(a["teacher_ids"]) > 1

    phase1 = [a for a in assignments if is_double(a) and not is_coteach(a)]
    phase1.sort(key=lambda a: _dept_sort_key(teachers.get(a["teacher_ids"][0], {}).get("department"), priority_order))

    phase2 = (
        [a for a in assignments if is_coteach(a) and a["is_scout"]]
        + [a for a in assignments if is_coteach(a) and not a["is_scout"] and is_double(a)]
        + [a for a in assignments if is_coteach(a) and not a["is_scout"] and not is_double(a)]
    )

    phase3 = [a for a in assignments if not is_coteach(a) and not is_double(a)]

    queue = phase1 + phase2 + phase3
    placed, unplaced, warnings = [], [], []

    for a in queue:
        blocks = a["period_split"]
        entry_ids_this_assignment = []
        success = True

        for block_size in blocks:
            best_slot, best_score = None, None
            for day in DAYS:
                if block_size == 1 and _subject_already_on_day(occupied, day, a["classroom_ids"], a["subject_id"]):
                    continue
                for start_period in PERIODS:
                    if start_period + block_size - 1 > PERIODS[-1]:
                        continue
                    period_range = list(range(start_period, start_period + block_size))
                    if not _slot_is_free(occupied, blocked_teacher_slots, blocked_classroom_slots, classrooms, day, period_range, a):
                        continue
                    exceeds = any(
                        _would_exceed_consecutive(teacher_day_periods, t, day, p)
                        for t in a["teacher_ids"] for p in period_range
                    )
                    score = 1 if exceeds else 0
                    if best_score is None or score < best_score:
                        best_score, best_slot = score, (day, period_range, exceeds)
                        if score == 0:
                            break
                if best_score == 0:
                    break

            if best_slot is None:
                success = False
                break

            day, period_range, exceeds = best_slot
            if exceeds:
                warnings.append(
                    f"{subjects.get(a['subject_id'], {}).get('subject_name', '?')}: ครูอาจต้องสอนติดกันเกิน 2 คาบ (วัน {day} คาบ {period_range[0]}-{period_range[-1]})"
                )
            # เลือกห้องปฏิบัติการที่ว่างตลอดทั้ง block (ห้องเดียวกันทุกคาบในคาบคู่) จากตัวเลือกที่ครูวิชานี้เลือกไว้
            chosen_room_id = _pick_available_room(occupied, day, period_range, a.get("room_ids") or [])
            if chosen_room_id is False:
                # ไม่ควรเกิดเพราะ _slot_is_free เช็คไปแล้ว แต่กันไว้เผื่อสภาวะแข่งกันของ block อื่นในลูปเดียวกัน
                success = False
                break
            for p in period_range:
                entry_data = {
                    "term_id": a["term_id"],
                    "day_of_week": day,
                    "period_number": p,
                    "subject_id": a["subject_id"],
                    "teacher_ids": a["teacher_ids"],
                    "classroom_ids": a["classroom_ids"],
                    "room_id": chosen_room_id,
                    "assignment_id": a["id"],
                    "note": None,
                    "source": "auto",
                    "created_by_name": "ระบบจัดตารางอัตโนมัติ",
                    "year_key": year_key,
                }
                _, doc_ref = db.collection("schedule_entries").add(entry_data)
                entry_ids_this_assignment.append(doc_ref.id)

                key = (day, p)
                slot = occupied.setdefault(key, {"teachers": set(), "classrooms": set(), "rooms": set(), "subj_by_class": {}})
                slot["teachers"].update(a["teacher_ids"])
                slot["classrooms"].update(a["classroom_ids"])
                if chosen_room_id:
                    slot["rooms"].add(chosen_room_id)
                for c in a["classroom_ids"]:
                    slot["subj_by_class"].setdefault(c, set()).add(a["subject_id"])
                for t in a["teacher_ids"]:
                    teacher_day_periods.setdefault((t, day), []).append(p)

        if success:
            placed.append(a["id"])
        else:
            for eid in entry_ids_this_assignment:
                db.collection("schedule_entries").document(eid).delete()
            unplaced.append({
                "assignment_id": a["id"],
                "subject_name": subjects.get(a["subject_id"], {}).get("subject_name", "ไม่ทราบวิชา"),
                "reason": "หาคาบว่างที่ไม่ชนกันไม่ได้ ต้องจัดด้วยมือผ่านหน้า 'จัดตารางสอน Manual'",
            })

    return {
        "placed_count": len(placed),
        "total": len(queue),
        "unplaced": unplaced,
        "warnings": warnings,
    }

class SolveRequest(BaseModel):
    term_id: Optional[str] = None

@app.post("/solve/")
async def solve_schedule(data: SolveRequest, year_key: Optional[str] = None, admin: dict = Depends(require_admin)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        return run_auto_solver(data.term_id, year_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- IMPORT APIs (รองรับทั้ง .csv และ .xlsx) ---

@app.post("/import/rooms/")
async def import_rooms(file: UploadFile = File(...), year_key: Optional[str] = Form(None), user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        contents = await file.read()
        df = _read_table(contents, file.filename)

        # แผนที่ "เกรด/ห้อง" -> classroom id (สำหรับผูกห้องประจำชั้น จากคอลัมน์ที่ 3)
        # รวมทั้งห้องเรียนของปีนี้ และห้องเรียนเก่าที่ยังไม่มี year_key (ข้อมูลก่อนมีระบบปีการศึกษา)
        # กันปัญหาผูกไม่ติดเพราะห้องเรียนถูกอัปโหลดไว้ก่อนเลือกปีการศึกษา
        classrooms_by_label = {}
        for cdoc in db.collection("classrooms").stream():
            cdata = cdoc.to_dict()
            doc_year_key = cdata.get("year_key")
            if year_key and doc_year_key and doc_year_key != year_key:
                continue
            label = f"{cdata.get('grade_level', '')}/{cdata.get('room_name', '')}".strip().replace(" ", "")
            if label != "/":
                classrooms_by_label[label] = cdoc.id

        count = 0
        unmatched_links = []
        for _, row in df.iterrows():
            room_name = _get_col(row, 'room_name')
            if not room_name:
                continue
            room_type = _normalize_room_type(_get_col(row, 'room_type', default="ห้องปฏิบัติการ"))
            home_classroom_id = None
            home_classroom_raw = _get_col(row, 'home_classroom', 'ห้องประจำของ', 'ห้องประจำ', 'classroom', 'ห้องเรียน')
            if home_classroom_raw and home_classroom_raw.strip() not in ("-", "—", "ไม่มี"):
                key = home_classroom_raw.strip().replace(" ", "")
                home_classroom_id = classrooms_by_label.get(key)
                if home_classroom_id:
                    room_type = "ห้องประจำชั้น"
                else:
                    unmatched_links.append(f"{room_name} -> {home_classroom_raw}")
            db.collection("rooms").add({
                "room_name": room_name,
                "room_type": room_type,
                "home_classroom_id": home_classroom_id,
                "year_key": year_key,
            })
            count += 1
        detected = {
            "room_name": _detect_col(df.columns, 'room_name'),
            "room_type": _detect_col(df.columns, 'room_type'),
            "home_classroom": _detect_col(df.columns, 'home_classroom', 'ห้องประจำของ', 'ห้องประจำ', 'classroom', 'ห้องเรียน'),
        }
        return {
            "status": "success",
            "imported_count": count,
            "detected_columns": detected,
            "file_columns": list(df.columns),
            "unmatched_links": unmatched_links,
        }
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/import/teachers/")
async def import_teachers(file: UploadFile = File(...), year_key: Optional[str] = Form(None), user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        contents = await file.read()
        df = _read_table(contents, file.filename)
        count = 0
        for _, row in df.iterrows():
            full_name = _get_col(row, 'full_name')
            if not full_name:
                continue
            db.collection("teachers").add({
                "full_name": full_name,
                "department": _get_col(row, 'department', 'กลุ่มสาระ'),
                "teacher_code": _get_col(row, 'teacher_code', 'old_teacher_code', 'รหัส') or None,
                "year_key": year_key,
            })
            count += 1
        detected = {
            "full_name": _detect_col(df.columns, 'full_name'),
            "department": _detect_col(df.columns, 'department', 'กลุ่มสาระ'),
            "teacher_code": _detect_col(df.columns, 'teacher_code', 'old_teacher_code', 'รหัส'),
        }
        return {"status": "success", "imported_count": count, "detected_columns": detected, "file_columns": list(df.columns)}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/import/subjects/")
async def import_subjects(file: UploadFile = File(...), year_key: Optional[str] = Form(None), user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        contents = await file.read()
        df = _read_table(contents, file.filename)
        count = 0
        for _, row in df.iterrows():
            subject_code = _get_col(row, 'subject_code')
            subject_name = _get_col(row, 'subject_name')
            if not subject_code or not subject_name:
                continue
            db.collection("subjects").add({"subject_code": subject_code, "subject_name": subject_name, "year_key": year_key})
            count += 1
        detected = {
            "subject_code": _detect_col(df.columns, 'subject_code'),
            "subject_name": _detect_col(df.columns, 'subject_name'),
        }
        return {"status": "success", "imported_count": count, "detected_columns": detected, "file_columns": list(df.columns)}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

@app.post("/import/classrooms/")
async def import_classrooms(file: UploadFile = File(...), year_key: Optional[str] = Form(None), user: dict = Depends(get_current_user)):
    if not db: raise HTTPException(status_code=500, detail="Firestore not initialized")
    try:
        contents = await file.read()
        df = _read_table(contents, file.filename)
        count = 0
        for _, row in df.iterrows():
            grade_level = _get_col(row, 'grade_level')
            room_name = _get_col(row, 'room_name')
            if not grade_level or not room_name:
                continue
            db.collection("classrooms").add({"grade_level": grade_level, "room_name": room_name, "year_key": year_key})
            count += 1
        detected = {
            "grade_level": _detect_col(df.columns, 'grade_level'),
            "room_name": _detect_col(df.columns, 'room_name'),
        }
        return {"status": "success", "imported_count": count, "detected_columns": detected, "file_columns": list(df.columns)}
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
