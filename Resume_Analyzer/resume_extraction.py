from .preprocessing import clean_text
from .extractors import file_format_router
from .parsing.section_segmentor import segment_resume
from .contact_extractor.personal_info_extractor import extract_personal_info
from .skills.extract_skills import find_skills_overlap_safe
from .parsing.education_extractor import extract_education_history
from .parsing.experience_extractor import extract_experience_info
from .parsing.project_extractor import extract_all_projects
from .parsing.certificate_extractor import extract_certificates
from .parsing.combined_section_handler import classify_education_certification_lines
from .parsing.leadership_extractor import extract_leadership_info


def extract_resume(filename):
    extracted_info = {
        "personal_info": {},
        "skills": [],
        "education": {},
        "experience": [],
        "projects": [],
        "certifications": [],
        "leadership": [],
        "metadata": {}
    }

    raw_text, used_xml_fallback = file_format_router(filename)

    extracted_info["metadata"].update({
        "used_fallback_extraction": used_xml_fallback
    })

    cleaned_text = clean_text(raw_text)
    sections = segment_resume(cleaned_text)

    # Personal information
    info = sections.get("info")
    extracted_info["personal_info"] = (
        extract_personal_info(info) if info else {}
    )

    # Skills
    skills = sections.get("skills")
    extracted_info["skills"] = (
        find_skills_overlap_safe("\n".join(skills)) if skills else []
    )

    # Education & Certifications
    education = sections.get("education")

    if not education:
        education_and_certification = sections.get("education & certification")

        if education_and_certification:
            education_certification = classify_education_certification_lines(
                education_and_certification
            )

            extracted_info["education"] = education_certification["education"]
            extracted_info["certifications"] = education_certification["certification"]

    else:
        extracted_info["education"] = extract_education_history(education)

        certifications = sections.get("certifications")
        extracted_info["certifications"] = (
            extract_certificates(certifications)
            if certifications else []
        )

    # Experience
    experience = sections.get("experience")
    extracted_info["experience"] = (
        extract_experience_info(experience) if experience else []
    )

    # Projects
    projects = sections.get("projects")
    extracted_info["projects"] = (
        extract_all_projects(projects) if projects else []
    )

    # Leadership
    leadership = sections.get("leadership")
    extracted_info["leadership"] = (
        extract_leadership_info(leadership) if leadership else []
    )

    return extracted_info