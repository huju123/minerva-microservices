from .section_segmentor import segment_resume
from .loaders.field_loaders import load_education_field_dict
from .loaders.field_loaders import load_institution_keywords_list
from .loaders.field_loaders import load_degree_keywords_list
from .experience_extractor import match_date_pattern
import re



def extract_education_history(text):
    edu_history = []
    education = {"latest_gpa": "",
                     "education_history" : []}
    
    gpa = extract_gpa("\n".join(text))
    institution_names = extract_institution(text)
    degrees = extract_degree(text)
    labeled_fields = extract_all_education_fields(text) # returns a dict
    # print(f"institution : {institution_names} | degrees = {degrees} |labeled_fields: {labeled_fields}")
    for institution, degrees, fields in zip (institution_names, degrees, labeled_fields):
        edu_history.append({"institution" : institution ,"degrees" : degrees, "edu_fields": labeled_fields})
    # print(edu_history)
    education["latest_gpa"] = gpa
    education["education_history"] = edu_history
    
    return education
    
def extract_gpa(text):
    pattern = r"GPA\s*:\s*\d\.\d+(/\d+(\.\d+)?)?"
    result = re.search(pattern, text)
    if result:
        return result.group()
    return None

def extract_labeled_field(text, label):
    pattern = re.escape(label) + r"\s*:\s*(.+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1)   
    else:
        return None
    

def extract_section_field(text, canonical_field_name):
    field_headers = load_education_field_dict()
    joined_string = "\n".join(text)
    variants = field_headers[canonical_field_name]

    for variant in variants:
        result = extract_labeled_field(joined_string, variant)
        if result:
            return result       
    result_dict = segment_resume(joined_string, field_headers)
    return "\n".join(result_dict.get(canonical_field_name, []))

def extract_all_education_fields(text):
    results = {}
    field_headers = load_education_field_dict()
    for key in field_headers:
        results[key] = extract_section_field(text, key)
    return results

# def extract_institution(text):
#     institutions = []
#     for line in text:
#         result = check_institution_keywords_in_lines(line)
#         if result:
#             # print(result.group())
#             if "|" in line:
#                 output = line.split("|")
#             elif "-" in line:
#                 output = line.split("-")
#             else:
#                 output = [line]

#             index = 1 if (result.start() >= 5 and len(output) > 1) else 0
#             institutions.append(output[index].strip())
#             # print(output[index])
#     return institutions

def extract_institution(text):
    institutions = []
    for line in text:
        result = check_institution_keywords_in_lines(line)
        if result:
            start, end = result.start(), result.end()
            
            left_boundary = 0
            for ch in ["|", "(", ")", "from", "in"]:
                pos = line.rfind(ch, 0, start)
            if pos > left_boundary:
                left_boundary = pos + 1
                
            pos = line.rfind(" - ", 0, start)
            if pos + 3 > left_boundary:
                left_boundary = pos + 3
            pos = line.rfind(" from ", 0, start)
            if pos + 6 > left_boundary:
                left_boundary = pos + 6

            pos = line.rfind(" in ", 0, start)
            if pos + 4 > left_boundary:
                left_boundary = pos + 4
                
            right_boundary = len(line)
            for ch in ["|", "(", ")"]:
                pos = line.find(ch, end)
            if pos != -1 and pos < right_boundary:
                right_boundary = pos
                
            right_dash = line.find(" - ", end) 
            if right_dash != -1 and right_dash < right_boundary:
                right_boundary = right_dash

            right = line.rfind(" from ", end)
            if right != -1 and right < right_boundary:
                right_boundary = right

            right = line.rfind(" in ", end)
            if right != -1 and right < right_boundary:
                right_boundary = right

            institution = (line[left_boundary : right_boundary]).strip()
            institutions.append(institution)
    return institutions
    
def check_institution_keywords_in_lines(line):
    keywords = load_institution_keywords_list()
    for each in keywords:
        pattern = r"(?<!\w)" + re.escape(each) + r"(?!\w)"
        result = re.search(pattern, line, re.IGNORECASE)
        if result:
            return result
    return None

def extract_degree(text):
    degrees = []
    pattern = r"(?<!\w)in(?!\w)"
    for i, line in enumerate(text):
        result = check_degree_keywords_in_lines(line)
        if result:
            # matched_line = None
            line = re.sub(r"^-\s*", "", line)
            # print(line)
            match = re.search(pattern, line)
            date_match = match_date_pattern(line)
            if date_match:
                matched_line = line[ : date_match.start()]
            else:
                matched_line = line
            if len(line.split())<5:
                output = matched_line + " " + text[i + 1] 
                degrees.append(output.strip()) 
            else:
                sep = "|" if "|" in matched_line else " - " if " - " in matched_line else " from "
                # print(sep)
                output = matched_line.split(sep)
                degrees.append(output[0].strip())
    return degrees
            
            
def check_degree_keywords_in_lines(line):
    keywords = load_degree_keywords_list()
    sorted_degrees = sorted(keywords, key=len, reverse=True)
    for each in sorted_degrees:
        pattern = r"(?<!\w)" + re.escape(each) + r"(?!\w)"
        result = re.search(pattern, line)
        if result:
            return result.group()
    return None