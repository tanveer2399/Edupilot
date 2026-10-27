from pydantic import BaseModel, ConfigDict, EmailStr


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: str
    full_name: str
    email: EmailStr
    department: str
    semester: int
