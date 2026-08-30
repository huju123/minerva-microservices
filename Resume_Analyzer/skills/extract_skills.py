from .skill_loader import load_skill_list
from .skill_loader import load_cannonical_skill_terms_dict
from .skill_loader import load_stack_expansions_dict
import re

skill_categories = {}
cannon_skills = load_skill_list()
for key in cannon_skills.keys():
    for each in cannon_skills[key]:
        skill_categories.update({each: key})
stack_expansions = load_stack_expansions_dict()
cannon_terms = load_cannonical_skill_terms_dict()

def find_skills_overlap_safe(text):
    accepted_ranges = []
    matches = []
    output = {}
    stacks = check_stack_expansions(text)
    matches.extend(stacks)
    for key in cannon_terms.keys():
        sorted_skills = sorted(cannon_terms[key], key=len, reverse=True) 
        for term in sorted_skills:
            pattern = r"(?<!\w)" + re.escape(term) + r"(?!\w)"
            result = re.search(pattern, text, re.IGNORECASE)
            if result:
                start = result.start()
                end = result.end()
                flag = False
                for each in accepted_ranges:
                    # print(each[0], " ",each[1]," ", start," ", end)
                    flag = flag or ranges_overlap(each[0], each[1], start, end)
                if not flag:
                    matches.append(key)
                    accepted_ranges.append([start, end])
    matches = set(matches)
    matches = list(matches)
    for skill in matches:
        if skill in skill_categories.keys():
            output.setdefault(skill_categories[skill], [])
            output[skill_categories[skill]].append(skill)
            
    # for key in skill_categories.keys():
    #     if key in matches:
            
    return output

    # for skill in sorted_skills:
    #     pattern = r"(?<!\w)" + re.escape(skill) + r"(?!\w)"
    #     result = re.search(pattern, text)
    #     if result:
    #         start = result.start()
    #         end = result.end()
    #         flag = False
    #         for each in accepted_ranges:
    #             flag = flag or ranges_overlap(each[0], each[1], start, end)
    #         if not flag:
    #             matches.append(skill)
    #             accepted_ranges.append([start, end])

    # return matches

def check_stack_expansions(text):
    expanded = []
    for key in stack_expansions.keys():
        pattern = r"(?<!\w)" + re.escape(key) + r"(?!\w)"
        result = re.search(pattern, text)
        if result:
            for skill in stack_expansions[key]:
                expanded.append(skill)
    expanded = set(expanded)
    expanded = list(expanded)
    return expanded

def ranges_overlap(start1, end1, start2, end2):
    if not (end1<=start2 or end2<=start1):
        return True
    else:
        return False