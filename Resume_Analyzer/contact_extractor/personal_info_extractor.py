from .name_extractor import extract_name
from .email_extractor import extract_email
from .phone_extractor import extract_phone_no

def extract_personal_info(text):
    personal_info = {"name": "", "email": "" , "phone_no": "" }
    
    personal_info["name"] = extract_name(text)
    personal_info["email"] = extract_email("\n".join(text))
    personal_info["phone_no"] = extract_phone_no("\n".join(text))

    return personal_info
    
    