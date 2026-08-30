from .loaders.field_loaders import load_months_list
from .loaders.field_loaders import load_job_title_keywords_list
from ..preprocessing.remove_whitespace import normalize_whitespace
import re

months = load_months_list()
month_alternatives = "|".join(months)
single_point = r"(?:(?:" + month_alternatives + r")\.?\s*\d{4}|\d{4})"
date_pattern = r"\s*"+single_point+r"\s*-\s*(?:"+single_point+r"|Present)"

def extract_experience(text):
    exp_index = []
    experience = []
    # titles = extract_title(text)
    for i,lines in enumerate(text):
        match = match_date_pattern(lines)
        # result = match.group()
        if match:
            exp_index.append(i)
    if not exp_index:
        return None
    # if exp_index[0] != 0:
    #     exp_index[0] = 0
    # for index, value in enumerate(exp_index):
    #     if index+1 == len(exp_index):
    #         experience.append(text[value + 2: ])
    #     else:
    #         next_index = exp_index[index + 1]
    #         experience.append(text[value + 2 : next_index]) 
       
    #     if index+1 == len(exp_index):
    #         experience.append(text[value+1: ])
    #     else:
    #         next_index = exp_index[index + 1]
    #         experience.append(text[value +1 : next_index])  

    return exp_index


def extract_experience_description(text, titles):
    exp_index = []
    desc = []
    # titles = extract_title(text)
    for i,lines in enumerate(text):
        match = match_date_pattern(lines)
        # result = match.group()
        if match:
            exp_index.append(i)
    if not exp_index:
        return None

    for index, value in enumerate(exp_index):
        if index + 1 == len(exp_index):
            next_index = len(text)
        else:
            next_index = exp_index[index + 1]

        gap = next_index - (value + 1)
        if gap <= 0:
            desc.append([])
        elif text[value + 1] == titles[index]:
            desc.append(text[value + 2 : next_index])
        else:
            if next_index != len(text):
                desc.append(text[value + 1 : next_index - 2])
            else:
                desc.append(text[value + 1 : next_index])
         
    return desc

def match_date_pattern(line):
    result = re.search(date_pattern, line)
    if result:
        return result
    return None


def extract_title_and_company(text):
    titles = []
    companies = []
    job_keywords = load_job_title_keywords_list()
    for index, line in enumerate(text):
        line = re.sub(r"^-\s*", "", line)
        match = match_date_pattern(line.strip())
        if not match:
            continue
        if match.start() > 5:
            prefix = line[:match.start()]
            has_title_keyword = any(re.search(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", prefix, re.IGNORECASE) for kw in job_keywords)

            sep  = None
            if "|" in prefix:
                sep_pattern = r"\|"
            elif re.search(r"\s-\s", prefix):
                sep_pattern = r"\s-\s"
            elif re.search(r"(?<!\w)at(?!\w)", prefix):
                sep_pattern = r"(?<!\w)at(?!\w)"
                
            if has_title_keyword and sep_pattern:
                parts = re.split(sep_pattern, prefix, maxsplit=1)
                title = re.sub(r"\(\s*$", "", parts[0].strip()).strip()
                company = re.sub(r"\(\s*$", "", parts[1].strip()).strip() if len(parts) > 1 else None
                titles.append(title)
                companies.append(company)
            else:
                company = re.sub(r"\(\s*$", "", prefix.strip()).strip()
                companies.append(company)
                titles.append(text[index + 1] if index + 1 < len(text) else None)
        else:
            if index == 0 or index - 2 < 0:
                titles.append(None)
            else:
                titles.append(text[index - 2])
            companies.append(text[index - 1] if index >= 1 else None)
    return titles, companies



def extract_experience_info(text):
    experience_info = []
    titles, companies = extract_title_and_company(text)
    descriptions = extract_experience_description(text, titles)
    # print(f"companes : {companies} | titles = {titles} |descriptions: {descriptions}")
    if not descriptions:
        descriptions = []
    for title, company, desc in zip (titles, companies, descriptions):
        experience_info.append({"title" : title, "company" : company ,"description" : desc})
    return experience_info
    
# def job_details_router(line):
#     match = match_date_pattern(line.strip())
#     if match:
#         if match.start()<=5:
#              return False
#         else:
#             return match
#     return None