from .resume_extraction import extract_resume
from .analysis.resume_analysis import analyze_resume

def evaluate_resume(filepath):
    try:
        extracted_info = extract_resume(filepath)
        analysis_result = analyze_resume(extracted_info, profile = "internship")

        return{
            "success" : True,
            "data" : {
                "analysis_result": analysis_result
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)} 
