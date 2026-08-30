from ..preprocessing.remove_whitespace import normalize_whitespace
from .loaders.field_loaders import load_months_list
import re

months = load_months_list()
month_alternatives = "|".join(months)
single_point = r"(?:(?:" + month_alternatives + r")\.?\s*\d{4}|\d{4})"
date_pattern = r"\s*"+single_point+r"\s*-\s*(?:"+single_point+r"|Present)"

def extract_leadership(text):
    date_index = []
    entries = []
    for i,lines in enumerate(text):
        match = match_date_pattern(lines)
        # result = match.group()
        if match:
            date_index.append(i)
    if not date_index and text:
        entries.append(text)
        print(entries)
    for index, value in enumerate(date_index):
        if index + 1 == len(date_index):
            entries.append(text[value + 1 : ])
        else:
            next_index = text[index + 1]
            entries.append(text[value + 1 : next_index] )
    return entries


def extract_leadership_description(text, titles):
    date_index = []
    desc = []
    for i,lines in enumerate(text):
        match = match_date_pattern(lines)
        if match:
            date_index.append(i)
    if not date_index:
        return None
    for index, value in enumerate(date_index):
        if text[value + 1] == titles[index]:
            if index+1 == len(date_index):
                desc.append(text[value + 2: ])
            else:
                next_index = date_index[index + 1]
                desc.append(text[value + 2 : next_index]) 
        else: 
            if index+1 == len(date_index):
                desc.append(text[value+1: ])
            else:
                next_index = date_index[index + 1]
                desc.append(text[value +1 : next_index - 2])  

    return desc


def match_date_pattern(line):
    result = re.search(date_pattern, line)
    if result:
        return result
    return None

def extract_location(text):
    company = []
    for index, line in enumerate(text):
        match = match_date_pattern(line.strip())
        if match:
            if match.start() <= 5:
                if index == 0:
                    return None
                company.append(text[index - 1])
            else:          
                result = line[: match.start()]
                result = result.replace("|", "")
                result = result.replace("\\t", "")
                result = normalize_whitespace(result)
                company.append(result)

    return company 

def extract_title(text):
    title = []
    for index, line in enumerate(text):
        match = match_date_pattern(line.strip())
        if match:
            if match.start() <= 5:
                if index == 0 or index - 2 <0:
                    continue
                title.append(text[index - 2])
            else:
                if index + 1 >= len(text):
                    continue
                result = text[index + 1]
                # result = result.replace("|", "")
                result = result.replace("\\t", "")
                result = normalize_whitespace(result)
                title.append(result)
    
    return title 

def extract_leadership_info(text):
    leadership_info = []
    locations = extract_location(text)
    titles = extract_title(text)
    descriptions = extract_leadership_description(text, titles)
    if not descriptions:
        return []
    # print(f"companes : {locations} | titles = {titles} |descriptions: {descriptions}")
    for title, loc, desc in zip (titles, locations, descriptions):
        leadership_info.append({"title" : title, "location" : loc ,"description" : desc})
    return leadership_info