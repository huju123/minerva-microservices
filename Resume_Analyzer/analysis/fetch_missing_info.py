def check_missing_info(extracted_info):
    missing_info = {

        "education" : {},
    }
    result = []
    personal_missing = [field for field in ["name", "email", "phone_no"] if not extracted_info["personal_info"].get(field)]
    if personal_missing:
        missing_info.update({"personal_info": personal_missing})
    if not extracted_info["skills"]:
        missing_info.update({"skills": "Missing"}) 
    if not extracted_info["education"].get("latest_gpa"):
        missing_info["education"].update({"latest_gpa" : "Missing"})
    if not extracted_info["education"].get("education_history"):
        missing_info["education"].update({"edu_history": "Missing"})
    else:
        edu_list = find_missing_fields_in_entries(extracted_info["education"]["education_history"],["institution", "degrees"], "institution")
        missing_info["education"].update({"education_history" : edu_list}) 
        if not missing_info["education"]["education_history"]:
            missing_info["education"].pop("education_history")
    
    
    if not extracted_info["projects"]:
        missing_info.update({"projects" : "Missing"})
    else:
        projects_list = find_missing_fields_in_entries(extracted_info["projects"], ["name", "tech_stack", "description"], "name")
        missing_info.update({"projects": projects_list}) if projects_list else []
    if not extracted_info["experience"]:
        missing_info.update({"experience" : "Missing"})
    else:
        exp_list = find_missing_fields_in_entries(extracted_info["experience"], ["title", "company", "description"], "title")
        missing_info.update({"experience": exp_list}) if exp_list else []
    if not extracted_info["certifications"]:
        missing_info.update({"certifications" : "Missing" })
    for key in missing_info.keys():
        if not missing_info.get(key):
            result.append(key)
    for each in result:
        missing_info.pop(each)
    return missing_info


def find_missing_fields_in_entries(entries, expected_fields, label_fields):
    missing_entries = []
    for entry in entries:
        missing = [field for field in expected_fields if not entry.get(field)]
        if missing:
            missing_entries.append({
                "entry": entry.get(label_fields, "Unknown"),
                "missing": missing
            })
    return missing_entries