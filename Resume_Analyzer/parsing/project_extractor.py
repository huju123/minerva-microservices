from .loaders.field_loaders import load_months_list
from preprocessing.remove_whitespace import normalize_whitespace
from skills.extract_skills import find_skills_overlap_safe
import re

months = load_months_list()
month_alternatives = "|".join(months)
date_pattern = r"(?:(?:" + month_alternatives + r")\.?\s*\d{4}|\d{4})"


def extract_project_description(text):
    project_desc_index = []
    projects = {"tech_stack": [], "description": []}
    for i,lines in enumerate(text):
        match = match_date_pattern(lines)
        # result = match.group()
        if match:
            project_desc_index.append(i)
    if not project_desc_index:
        return None
    for index, value in enumerate(project_desc_index):
     
        if index+1 == len(project_desc_index):
            projects["description"].append(text[value+1: ])
            projects["tech_stack"].append(find_skills_overlap_safe("\n".join(text[value: ])))
        else:
            next_index = project_desc_index[index + 1]
            projects["description"].append(text[value+1 : next_index])   
            projects["tech_stack"].append(find_skills_overlap_safe("\n".join(text[value:next_index])))

    return projects

def extract_project_name(text):
    # project_name = {"names": [], "tech_stack" :[]}
    project_names = []
    for index, line in enumerate(text):
        match = match_date_pattern(line.strip())
        if match:      
            # result = line[: match.start()]
            sep = "|" if "|" in line else "-" 
            parts = line[:match.start()].split(sep) 
            name = parts[0].strip()
            # tech_stack = parts[1].strip() if len(parts) > 1 else None
            name = normalize_whitespace(name)
            # tech_stack = normalize_whitespace(tech_stack)
            project_names.append(name)
            # project_name["tech_stack"].append(tech_stack)

    return project_names


def match_date_pattern(line):
    result = re.search(date_pattern, line)
    if result:
        return result
    return None

def extract_all_projects(text):
    names = extract_project_name(text)
    projects_info = extract_project_description(text)
    if not projects_info:
        return []
    projects_list = []
    # print("names : ", names,"| tech_stack = ", projects_info)
    for name, tech, desc in zip (names, projects_info["tech_stack"], projects_info["description"]):
        projects_list.append({"name" : name, "tech_stack" : tech ,"description" : desc})
    return projects_list

# def extract_tech_stack(name_lines):
#     tech_stacks = []
#     for each in name_lines:
#         parts = each[:]
        
