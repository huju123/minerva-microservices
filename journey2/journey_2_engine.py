"""
Journey 2 — Career-in-Mind Scoring Engine
Minerva Career Discovery Assessment v4

Responsibilities:
- Validate a selected career
- Load exactly 5 career-specific questions from assessment.json
- Score submitted answers server-side
- Calculate readiness percentage and performance level
- Build current-skill profile from normalized canonical skills
- Use career_skill_matrix.json as the sole source of target levels
- Calculate strengths, weak areas, skill gaps, and priorities
- Return a backend-friendly result payload

Security:
- Never expose correct_option through public question methods.
- Never expose answer keys to the frontend.
- Scoring remains server-side.
- Diagnostic signals are normalized through skill_normalization.json.
- Diagnostic-only signals never become formal canonical skills.
- Canonical target levels come only from career_skill_matrix.json.

Expected journey_2_skills.json structure:

{
    "careers": {
        "ui_ux": {
            "career_name": "...",
            "required_skills": [...],
            "question_skill_mapping": {...}
        },
        ...
    },
    "readiness_rules": {
        "performance_levels": [...],
        "validation_labels": [...]
    }
}
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping


# ============================================================
# CONSTANTS
# ============================================================

CAREER_IDS = (
    "ui_ux",
    "development",
    "data",
    "ai",
    "cyber",
)

ANSWER_OPTIONS = {"A", "B", "C", "D"}

# SKILL_LEVEL_LABELS = {
#     1: "Needs Foundation",
#     2: "Developing",
#     3: "Functional",
#     4: "Strong",
#     5: "Advanced",
# }
SKILL_LEVEL_LABELS = {
    1: "Beginner",
    2: "Novice",
    3: "Intermediate",
    4: "Advanced",
    5: "Expert",
}

PRIORITY_ORDER = {
    "High": 0,
    "Medium": 1,
    "Low": 2,
    "None": 3,
}

CATEGORY_ORDER = {
    "core": 0,
    "supporting": 1,
}


# ============================================================
# EXCEPTIONS
# ============================================================

class Journey2Error(Exception):
    """Base exception for Journey 2 errors."""


class InvalidCareerError(Journey2Error):
    """Raised when an unsupported career is selected."""


class InvalidAssessmentError(Journey2Error):
    """Raised when assessment or skills configuration is invalid."""


class InvalidAnswersError(Journey2Error):
    """Raised when submitted answers are invalid."""


# ============================================================
# MAIN ENGINE
# ============================================================

class Journey2ScoringEngine:
    """
    Scoring engine for Minerva Journey 2 — Career-in-Mind.

    The engine loads:
        1. assessment.json
        2. journey_2_skills.json

    It validates both files and provides methods for:
        - retrieving public career questions
        - scoring answers
        - calculating readiness
        - calculating skill profile
        - calculating skill gaps
        - generating next-step recommendations
    """

    def __init__(
        self,
        assessment_path: str | Path = "assessment.json",
        skills_path: str | Path = "journey_2_skills.json",
        matrix_path: str | Path = "career_skill_matrix.json",
        normalization_path: str | Path = "skill_normalization.json",
    ) -> None:

        self.assessment_path = Path(assessment_path)
        self.skills_path = Path(skills_path)
        self.matrix_path = Path(matrix_path)
        self.normalization_path = Path(normalization_path)

        self.assessment = self._load_json(self.assessment_path)
        self.skills_config = self._load_json(self.skills_path)
        self.career_skill_matrix = self._load_json(self.matrix_path)
        self.skill_normalization = self._load_json(self.normalization_path)

        self._validate_config()

    # ========================================================
    # JSON LOADING
    # ========================================================

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        """
        Load a JSON file and ensure it contains an object.
        """

        if not path.exists():
            raise FileNotFoundError(
                f"Required JSON file not found: {path}"
            )

        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)

        except json.JSONDecodeError as exc:
            raise InvalidAssessmentError(
                f"Invalid JSON in {path}: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise InvalidAssessmentError(
                f"{path} must contain a JSON object."
            )

        return data

    # ========================================================
    # CONFIGURATION VALIDATION
    # ========================================================

    def _validate_config(self) -> None:
        """
        Validate assessment.json and journey_2_skills.json.

        This method validates the exact schema used by the current
        Journey 2 JSON configuration.
        """

        self._validate_assessment()
        self._validate_skills_config()
        self._validate_canonical_matrix()
        self._validate_normalization()

    def _validate_assessment(self) -> None:
        """
        Validate assessment.json.

        Expected:
            questions.career_in_mind.<career> = exactly 5 questions
        """

        questions_root = self.assessment.get("questions")

        if not isinstance(questions_root, dict):
            raise InvalidAssessmentError(
                "assessment.json must contain a 'questions' object."
            )

        questions = questions_root.get("career_in_mind")

        if not isinstance(questions, dict):
            raise InvalidAssessmentError(
                "assessment.json must contain "
                "questions.career_in_mind."
            )

        for career in CAREER_IDS:

            career_questions = questions.get(career)

            if not isinstance(career_questions, list):
                raise InvalidAssessmentError(
                    f"Missing career_in_mind questions for "
                    f"'{career}'."
                )

            if len(career_questions) != 5:
                raise InvalidAssessmentError(
                    f"Career '{career}' must have exactly "
                    f"5 questions; found "
                    f"{len(career_questions)}."
                )

            question_ids = []

            for question in career_questions:

                if not isinstance(question, dict):
                    raise InvalidAssessmentError(
                        f"Question in career '{career}' "
                        f"must be an object."
                    )

                question_id = question.get("id")

                if not question_id:
                    raise InvalidAssessmentError(
                        f"Career '{career}' contains a "
                        f"question without an id."
                    )

                question_ids.append(question_id)

                if question.get("career") != career:
                    raise InvalidAssessmentError(
                        f"Question {question_id} has career "
                        f"{question.get('career')!r}, expected "
                        f"{career!r}."
                    )

                if question.get("score") != 1:
                    raise InvalidAssessmentError(
                        f"Question {question_id} must have "
                        f"score=1."
                    )

                correct_option = question.get(
                    "correct_option"
                )

                if correct_option not in ANSWER_OPTIONS:
                    raise InvalidAssessmentError(
                        f"Question {question_id} has an "
                        f"invalid correct_option."
                    )

            if len(question_ids) != len(set(question_ids)):
                raise InvalidAssessmentError(
                    f"Duplicate question ID found in "
                    f"career '{career}'."
                )

    def _validate_skills_config(self) -> None:
        """
        Validate journey_2_skills.json.

        Current schema uses:

            careers = {
                "ui_ux": {...},
                "development": {...},
                ...
            }

        rather than a list.
        """

        configured_careers = self.skills_config.get("careers")

        if not isinstance(configured_careers, dict):
            raise InvalidAssessmentError(
                "journey_2_skills.json must contain a "
                "'careers' object."
            )

        configured_ids = set(configured_careers.keys())

        missing = set(CAREER_IDS) - configured_ids

        if missing:
            raise InvalidAssessmentError(
                "journey_2_skills.json is missing careers: "
                f"{sorted(missing)}"
            )

        # Check for unexpected career IDs.
        unexpected = configured_ids - set(CAREER_IDS)

        if unexpected:
            raise InvalidAssessmentError(
                "journey_2_skills.json contains unsupported "
                f"career IDs: {sorted(unexpected)}"
            )

        questions = self.assessment["questions"][
            "career_in_mind"
        ]

        # Validate every career.
        for career in CAREER_IDS:

            career_config = configured_careers.get(career)

            if not isinstance(career_config, dict):
                raise InvalidAssessmentError(
                    f"Career '{career}' configuration must "
                    f"be an object."
                )

            career_name = career_config.get("career_name")

            if not isinstance(career_name, str) or not career_name.strip():
                raise InvalidAssessmentError(
                    f"Career '{career}' must contain a valid "
                    f"'career_name'."
                )

            required_skills = career_config.get(
                "required_skills"
            )

            if not isinstance(required_skills, list):
                raise InvalidAssessmentError(
                    f"Career '{career}' must contain "
                    f"'required_skills' as an array."
                )

            required_skill_ids = set()

            for skill in required_skills:

                if not isinstance(skill, dict):
                    raise InvalidAssessmentError(
                        f"Career '{career}' contains an invalid "
                        f"skill definition."
                    )

                skill_id = skill.get("id")

                if not isinstance(skill_id, str) or not skill_id:
                    raise InvalidAssessmentError(
                        f"Career '{career}' contains a skill "
                        f"without a valid id."
                    )

                if skill_id in required_skill_ids:
                    raise InvalidAssessmentError(
                        f"Duplicate skill '{skill_id}' found "
                        f"in career '{career}'."
                    )

                required_skill_ids.add(skill_id)

                skill_name = skill.get("name")

                if not isinstance(skill_name, str) or not skill_name.strip():
                    raise InvalidAssessmentError(
                        f"Skill '{skill_id}' in career "
                        f"'{career}' must contain a valid name."
                    )

                category = skill.get("category")

                if category not in {"core", "supporting"}:
                    raise InvalidAssessmentError(
                        f"Skill '{skill_id}' in career "
                        f"'{career}' must have category "
                        f"'core' or 'supporting'."
                    )

                target_level = skill.get("target_level")

                if not isinstance(target_level, int):
                    raise InvalidAssessmentError(
                        f"Skill '{skill_id}' in career "
                        f"'{career}' must have an integer "
                        f"target_level."
                    )

                if not 1 <= target_level <= 5:
                    raise InvalidAssessmentError(
                        f"Skill '{skill_id}' in career "
                        f"'{career}' has invalid target_level "
                        f"{target_level}. Expected 1-5."
                    )

            # ------------------------------------------------
            # Question → Skill Mapping
            # ------------------------------------------------

            question_skill_mapping = career_config.get(
                "question_skill_mapping"
            )

            if not isinstance(question_skill_mapping, dict):
                raise InvalidAssessmentError(
                    f"Career '{career}' must contain "
                    f"'question_skill_mapping' as an object."
                )

            expected_question_ids = {
                question["id"]
                for question in questions[career]
            }

            mapped_question_ids = set(
                question_skill_mapping.keys()
            )

            missing_question_mappings = (
                expected_question_ids - mapped_question_ids
            )

            if missing_question_mappings:
                raise InvalidAssessmentError(
                    f"Career '{career}' is missing skill "
                    f"mappings for question(s): "
                    f"{sorted(missing_question_mappings)}"
                )

            unexpected_question_mappings = (
                mapped_question_ids - expected_question_ids
            )

            if unexpected_question_mappings:
                raise InvalidAssessmentError(
                    f"Career '{career}' contains mappings for "
                    f"unknown question(s): "
                    f"{sorted(unexpected_question_mappings)}"
                )

            # Validate mapped skill IDs.
            for question_id, mapped_skills in (
                question_skill_mapping.items()
            ):

                if not isinstance(mapped_skills, list):
                    raise InvalidAssessmentError(
                        f"Mapping for {question_id} in career "
                        f"'{career}' must be an array."
                    )

                if not mapped_skills:
                    raise InvalidAssessmentError(
                        f"Question {question_id} in career "
                        f"'{career}' must map to at least "
                        f"one skill signal."
                    )

                for skill_id in mapped_skills:

                    if not isinstance(skill_id, str):
                        raise InvalidAssessmentError(
                            f"Skill mapping for question "
                            f"{question_id} in career "
                            f"'{career}' must contain strings."
                        )

                    # Diagnostic-only signals are allowed.
                    # They simply won't be included in the
                    # formal current skill profile unless they
                    # appear in required_skills.

        # ----------------------------------------------------
        # Validate skill level scale
        # ----------------------------------------------------

        skill_level_scale = self.skills_config.get(
            "skill_level_scale"
        )

        if not isinstance(skill_level_scale, dict):
            raise InvalidAssessmentError(
                "journey_2_skills.json must contain "
                "'skill_level_scale'."
            )

        scale_min = skill_level_scale.get("scale_min")
        scale_max = skill_level_scale.get("scale_max")

        if scale_min != 1 or scale_max != 5:
            raise InvalidAssessmentError(
                "skill_level_scale must use a 1-5 scale."
            )

        # ----------------------------------------------------
        # Validate readiness rules
        # ----------------------------------------------------

        readiness_rules = self.skills_config.get(
            "readiness_rules"
        )

        if not isinstance(readiness_rules, dict):
            raise InvalidAssessmentError(
                "journey_2_skills.json must contain "
                "'readiness_rules'."
            )

        performance_levels = readiness_rules.get(
            "performance_levels"
        )

        if not isinstance(performance_levels, list):
            raise InvalidAssessmentError(
                "readiness_rules must contain "
                "'performance_levels'."
            )

        validation_labels = readiness_rules.get(
            "validation_labels"
        )

        if not isinstance(validation_labels, list):
            raise InvalidAssessmentError(
                "readiness_rules must contain "
                "'validation_labels'."
            )

    # ========================================================
    # CANONICAL MATRIX VALIDATION
    # ========================================================

    def _validate_canonical_matrix(self) -> None:
        """Validate career_skill_matrix.json as the target source of truth."""

        careers = self.career_skill_matrix.get("careers")
        if not isinstance(careers, dict):
            raise InvalidAssessmentError(
                "career_skill_matrix.json must contain a 'careers' object."
            )

        configured_ids = set(careers.keys())
        expected_ids = set(CAREER_IDS)

        if configured_ids != expected_ids:
            raise InvalidAssessmentError(
                "career_skill_matrix.json career IDs must exactly match "
                f"{sorted(expected_ids)}; found {sorted(configured_ids)}."
            )

        for career in CAREER_IDS:
            config = careers[career]
            if not isinstance(config, dict):
                raise InvalidAssessmentError(
                    f"Canonical configuration for '{career}' must be an object."
                )

            career_name = config.get("career_name")
            if not isinstance(career_name, str) or not career_name.strip():
                raise InvalidAssessmentError(
                    f"Canonical career '{career}' must have a valid career_name."
                )

            required_skills = config.get("required_skills")
            if not isinstance(required_skills, dict) or not required_skills:
                raise InvalidAssessmentError(
                    f"Canonical career '{career}' must contain required_skills as a non-empty object."
                )

            for skill_id, definition in required_skills.items():
                if not isinstance(skill_id, str) or not skill_id:
                    raise InvalidAssessmentError(
                        f"Canonical career '{career}' contains an invalid skill ID."
                    )
                if not isinstance(definition, dict):
                    raise InvalidAssessmentError(
                        f"Canonical skill '{skill_id}' in '{career}' must be an object."
                    )
                target = definition.get("target_level")
                if not isinstance(target, int) or not 1 <= target <= 5:
                    raise InvalidAssessmentError(
                        f"Canonical skill '{skill_id}' in '{career}' has invalid target_level {target!r}."
                    )
                if definition.get("category") not in {"core", "supporting", "tool"}:
                    raise InvalidAssessmentError(
                        f"Canonical skill '{skill_id}' in '{career}' has invalid category."
                    )
                weight = definition.get("weight")
                if not isinstance(weight, (int, float)) or weight <= 0:
                    raise InvalidAssessmentError(
                        f"Canonical skill '{skill_id}' in '{career}' must have a positive numeric weight."
                    )

    # ========================================================
    # NORMALIZATION VALIDATION
    # ========================================================

    def _validate_normalization(self) -> None:
        """Validate source-signal → canonical-skill normalization."""

        mappings = self.skill_normalization.get("career_mappings")
        if not isinstance(mappings, dict):
            raise InvalidAssessmentError(
                "skill_normalization.json must contain career_mappings."
            )

        canonical_careers = self.career_skill_matrix["careers"]

        for career in CAREER_IDS:
            career_mappings = mappings.get(career)
            if not isinstance(career_mappings, dict):
                raise InvalidAssessmentError(
                    f"skill_normalization.json is missing mappings for '{career}'."
                )

            entries = career_mappings.get("mappings")
            if not isinstance(entries, list):
                raise InvalidAssessmentError(
                    f"Normalization mappings for '{career}' must be an array."
                )

            seen = set()
            canonical_ids = set(canonical_careers[career]["required_skills"].keys())

            for entry in entries:
                if not isinstance(entry, dict):
                    raise InvalidAssessmentError(
                        f"Invalid normalization entry in career '{career}'."
                    )

                source = entry.get("source_skill")
                target = entry.get("canonical_skill")
                mapping_type = entry.get("mapping_type")
                confidence = entry.get("confidence")

                if not isinstance(source, str) or not source:
                    raise InvalidAssessmentError(
                        f"Normalization entry in '{career}' has invalid source_skill."
                    )
                if source in seen:
                    raise InvalidAssessmentError(
                        f"Duplicate normalization source '{source}' in '{career}'."
                    )
                seen.add(source)

                if mapping_type not in {"exact", "semantic", "diagnostic_only"}:
                    raise InvalidAssessmentError(
                        f"Invalid mapping_type '{mapping_type}' for '{source}' in '{career}'."
                    )
                if confidence not in {"high", "moderate"}:
                    raise InvalidAssessmentError(
                        f"Invalid confidence '{confidence}' for '{source}' in '{career}'."
                    )

                if mapping_type == "diagnostic_only":
                    if target is not None:
                        raise InvalidAssessmentError(
                            f"Diagnostic-only signal '{source}' in '{career}' must have canonical_skill=null."
                        )
                else:
                    if not isinstance(target, str) or target not in canonical_ids:
                        raise InvalidAssessmentError(
                            f"Normalization target '{target}' for '{source}' in '{career}' "
                            "is not a canonical skill for that career."
                        )

            # Every signal used by the J2 question mappings must be normalized.
            j2_mapping = self.skills_config["careers"][career]["question_skill_mapping"]
            normalized_sources = seen
            missing_sources = {
                signal
                for signals in j2_mapping.values()
                for signal in signals
                if signal not in normalized_sources
            }
            if missing_sources:
                raise InvalidAssessmentError(
                    f"Career '{career}' has unmapped J2 diagnostic signals: "
                    f"{sorted(missing_sources)}"
                )

    # ========================================================
    # CANONICAL CAREER CONFIGURATION
    # ========================================================

    def _canonical_career_config(self, career: str) -> Dict[str, Any]:
        """Return canonical career requirements from career_skill_matrix.json."""

        career = self.normalize_career(career)
        return self.career_skill_matrix["careers"][career]

    # ========================================================
    # CAREER NORMALIZATION
    # ========================================================

    @staticmethod
    def normalize_career(career: str) -> str:
        """
        Normalize user-provided career names into official
        Minerva career IDs.
        """

        if not isinstance(career, str):
            raise InvalidCareerError(
                "Career must be a string."
            )

        value = career.strip().lower()

        aliases = {
            # UI/UX
            "ui/ux": "ui_ux",
            "ui ux": "ui_ux",
            "ui/ux design": "ui_ux",
            "ui ux design": "ui_ux",
            "ux": "ui_ux",
            "ux design": "ui_ux",
            "ui design": "ui_ux",

            # Development
            "development": "development",
            "software development": "development",
            "software developer": "development",
            "software engineering": "development",
            "software engineer": "development",
            "developer": "development",

            # Data
            "data": "data",
            "data analytics": "data",
            "data analyst": "data",
            "data science": "data",
            "data scientist": "data",
            "analytics": "data",

            # AI
            "ai": "ai",
            "ai/ml": "ai",
            "ai ml": "ai",
            "artificial intelligence": "ai",
            "machine learning": "ai",
            "machine learning engineer": "ai",
            "ml": "ai",

            # Cybersecurity
            "cyber": "cyber",
            "cybersecurity": "cyber",
            "cyber security": "cyber",
            "security analyst": "cyber",
            "information security": "cyber",
            "infosec": "cyber",
        }

        normalized = aliases.get(value, value)

        if normalized not in CAREER_IDS:
            raise InvalidCareerError(
                f"Unsupported career '{career}'. "
                f"Choose one of: {', '.join(CAREER_IDS)}."
            )

        return normalized

    # ========================================================
    # CAREER CONFIGURATION
    # ========================================================

    def _career_config(
        self,
        career: str,
    ) -> Dict[str, Any]:
        """
        Return the configuration for one career.

        journey_2_skills.json uses a careers dictionary.
        """

        career = self.normalize_career(career)

        careers = self.skills_config.get("careers", {})

        if career not in careers:
            raise InvalidAssessmentError(
                f"Career '{career}' not found in "
                f"journey_2_skills.json."
            )

        config = careers[career]

        if not isinstance(config, dict):
            raise InvalidAssessmentError(
                f"Configuration for career '{career}' "
                f"must be an object."
            )

        return config

    # ========================================================
    # PUBLIC QUESTIONS
    # ========================================================

    def get_career_questions(
        self,
        career: str,
    ) -> List[Dict[str, Any]]:
        """
        Return exactly 5 public questions for a career.

        Security:
        correct_option is intentionally removed.
        score is intentionally removed.
        """

        career = self.normalize_career(career)

        questions = self.assessment[
            "questions"
        ]["career_in_mind"][career]

        return [
            self._public_question(question)
            for question in questions
        ]

    @staticmethod
    def _public_question(
        question: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert an internal question into a frontend-safe
        question object.

        Answer key and score are never returned.
        """

        return {
            "id": question["id"],
            "title": question.get("title"),
            "type": question.get("type"),
            "interaction": question.get("interaction"),
            "instruction": question.get("instruction"),
            "options": question.get("options", []),
            "career": question.get("career"),
            "career_name": question.get("career_name"),
        }

    # ========================================================
    # SCORE ASSESSMENT
    # ========================================================

    def score_assessment(
        self,
        career: str,
        answers: Mapping[str, str],
    ) -> Dict[str, Any]:
        """
        Score exactly one selected career's 5 questions.

        Example:

            career = "data"

            answers = {
                "DATA_01": "A",
                "DATA_02": "B",
                "DATA_03": "C",
                "DATA_04": "A",
                "DATA_05": "D"
            }

        Returns:
            readiness
            performance
            validation
            strengths
            weak areas
            current skill profile
            skill gaps
            question results
            recommendation

        Never returns correct_option.
        """

        career = self.normalize_career(career)

        if not isinstance(answers, Mapping):
            raise InvalidAnswersError(
                "answers must be an object/dictionary."
            )

        questions = self.assessment[
            "questions"
        ]["career_in_mind"][career]

        expected_ids = {
            question["id"]
            for question in questions
        }

        submitted_ids = set(answers.keys())

        # ----------------------------------------------------
        # Missing answers
        # ----------------------------------------------------

        missing = sorted(
            expected_ids - submitted_ids
        )

        if missing:
            raise InvalidAnswersError(
                "Missing answers for question(s): "
                f"{', '.join(missing)}."
            )

        # ----------------------------------------------------
        # Extra answers
        # ----------------------------------------------------

        extra = sorted(
            submitted_ids - expected_ids
        )

        if extra:
            raise InvalidAnswersError(
                "Unexpected question ID(s): "
                f"{', '.join(extra)}."
            )

        # ----------------------------------------------------
        # Score questions
        # ----------------------------------------------------

        score = 0
        question_results: List[Dict[str, Any]] = []

        for question in questions:

            question_id = question["id"]

            answer = answers[question_id]

            if not isinstance(answer, str):
                raise InvalidAnswersError(
                    f"Answer for {question_id} must be "
                    f"A, B, C, or D."
                )

            answer = answer.strip().upper()

            if answer not in ANSWER_OPTIONS:
                raise InvalidAnswersError(
                    f"Invalid answer '{answer}' for "
                    f"{question_id}. "
                    f"Expected A, B, C, or D."
                )

            # Server-side answer key comparison.
            correct = (
                answer == question["correct_option"]
            )

            if correct:
                score += int(question["score"])

            question_results.append(
                {
                    "question_id": question_id,
                    "selected_option": answer,
                    "is_correct": correct,
                    "primary_dimension": question.get(
                        "primary_dimension"
                    ),
                    "secondary_dimension": question.get(
                        "secondary_dimension"
                    ),
                    "behavior_signals": question.get(
                        "behavior_signals",
                        [],
                    ),
                }
            )

        # ----------------------------------------------------
        # Readiness
        # ----------------------------------------------------

        max_score = sum(
            int(question["score"])
            for question in questions
        )

        readiness = (
            round((score / max_score) * 100, 2)
            if max_score
            else 0.0
        )

        # ----------------------------------------------------
        # Performance
        # ----------------------------------------------------

        performance = self._performance_level(
            readiness
        )

        # ----------------------------------------------------
        # Current skill profile
        # ----------------------------------------------------

        profile = self._build_current_skill_profile(
            career=career,
            question_results=question_results,
        )

        # ----------------------------------------------------
        # Skill gap
        # ----------------------------------------------------

        skill_gap = self._build_skill_gap(
            career=career,
            current_profile=profile,
        )

        # ----------------------------------------------------
        # Career metadata
        # ----------------------------------------------------

        career_info = self._canonical_career_config(career)

        career_name = career_info.get(
            "career_name",
            career,
        )

        validation = self._interest_validation(
            readiness
        )

        # ----------------------------------------------------
        # Final backend result
        # ----------------------------------------------------

        return {
            "career": career,
            "career_name": career_name,

            "score": score,
            "max_score": max_score,

            "readiness_percent": readiness,

            "performance_level": performance["level"],

            "performance_label": performance["label"],

            "validation": validation,

            "strengths": profile["strengths"],

            "weak_areas": profile["weak_areas"],

            "current_skill_profile": profile["skills"],

            "skill_gap": skill_gap,

            "question_results": question_results,

            "recommended_next_step": (
                self._recommended_next_step(
                    readiness,
                    skill_gap,
                )
            ),
        }

    # ========================================================
    # PERFORMANCE LEVEL
    # ========================================================

    def _performance_level(
        self,
        readiness: float,
    ) -> Dict[str, str]:
        """
        Determine performance level from
        readiness_rules.performance_levels.
        """

        readiness_rules = self.skills_config.get(
            "readiness_rules",
            {},
        )

        rules = readiness_rules.get(
            "performance_levels",
            [],
        )

        for rule in rules:

            minimum = float(
                rule.get("min_percent", 0)
            )

            maximum = float(
                rule.get("max_percent", 100)
            )

            if minimum <= readiness <= maximum:

                level = str(
                    rule.get(
                        "level",
                        "Unknown",
                    )
                )

                return {
                    "level": level,
                    "label": level,
                }

        # Safe fallback.
        if readiness >= 100:
            return {
                "level": "Highly Ready",
                "label": "Highly Ready",
            }

        if readiness >= 80:
            return {
                "level": "Strong Readiness",
                "label": "Strong Readiness",
            }

        if readiness >= 60:
            return {
                "level": "Developing",
                "label": "Developing",
            }

        if readiness >= 40:
            return {
                "level": "Early Development",
                "label": "Early Development",
            }

        return {
            "level": "Needs Foundation",
            "label": "Needs Foundation",
        }

    # ========================================================
    # VALIDATION LABEL
    # ========================================================

    def _interest_validation(
        self,
        readiness: float,
    ) -> str:
        """
        Determine validation label from
        readiness_rules.validation_labels.
        """

        readiness_rules = self.skills_config.get(
            "readiness_rules",
            {},
        )

        rules = readiness_rules.get(
            "validation_labels",
            [],
        )

        for rule in rules:

            minimum = float(
                rule.get("min_percent", 0)
            )

            maximum = float(
                rule.get("max_percent", 100)
            )

            if minimum <= readiness <= maximum:

                return str(
                    rule.get(
                        "label",
                        "Needs Development",
                    )
                )

        # Safe fallback.
        if readiness >= 80:
            return "Strong Match"

        if readiness >= 60:
            return "Good Match"

        if readiness >= 40:
            return "Emerging Match"

        return "Needs Development"

    # ========================================================
    # CURRENT SKILL PROFILE
    # ========================================================

    def _build_current_skill_profile(
        self,
        career: str,
        question_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build the formal current-skill profile using canonical skills.

        Flow:
            J2 question signals
                ↓
            skill_normalization.json
                ↓
            canonical skill IDs
                ↓
            evidence by question
                ↓
            current level

        Canonical target levels, categories, and weights come exclusively
        from career_skill_matrix.json. Diagnostic-only signals never become
        formal skill-profile entries.

        Important: no evidence is represented as ``current_level=None``
        rather than falsely treating the user as Beginner (level 1).
        """

        career = self.normalize_career(career)
        j2_config = self._career_config(career)
        canonical_config = self._canonical_career_config(career)
        canonical_skills = canonical_config["required_skills"]

        question_skill_mapping = j2_config.get("question_skill_mapping", {})
        normalization_entries = self.skill_normalization["career_mappings"][career]["mappings"]
        normalization = {
            entry["source_skill"]: entry
            for entry in normalization_entries
        }

        correctness_by_question = {
            item["question_id"]: bool(item["is_correct"])
            for item in question_results
        }

        # canonical_skill -> set(question_ids)
        # A question counts at most once for a canonical skill, even if
        # multiple source signals in that question normalize to the same skill.
        skill_question_map: Dict[str, set[str]] = {
            skill_id: set() for skill_id in canonical_skills
        }

        for question_id, source_signals in question_skill_mapping.items():
            if question_id not in correctness_by_question:
                continue

            for source_signal in source_signals:
                entry = normalization.get(source_signal)
                if not entry:
                    raise InvalidAssessmentError(
                        f"No normalization mapping for signal '{source_signal}' "
                        f"in career '{career}'."
                    )

                if entry["mapping_type"] == "diagnostic_only":
                    continue

                canonical_skill = entry["canonical_skill"]
                if canonical_skill in canonical_skills:
                    skill_question_map[canonical_skill].add(question_id)

        result: List[Dict[str, Any]] = []
        strength_items: List[Dict[str, Any]] = []
        weak_skill_items: List[Dict[str, Any]] = []

        for skill_id, definition in canonical_skills.items():
            skill_name = self._display_skill_name(skill_id)
            category = definition["category"]
            target_level = int(definition["target_level"])
            weight = float(definition["weight"])

            question_ids = sorted(skill_question_map.get(skill_id, set()))
            evidence = [
                correctness_by_question[qid]
                for qid in question_ids
                if qid in correctness_by_question
            ]

            total_signals = len(evidence)
            positive_signals = sum(1 for signal in evidence if signal)
            negative_signals = total_signals - positive_signals

            if total_signals == 0:
                current_level = None
                evidence_ratio = None
                gap = None
                gap_label = "No Evidence"
                priority = "None"
            else:
                evidence_ratio = positive_signals / total_signals

                # A high percentage from very few questions is not enough
                # evidence to claim an expert skill level.
                current_level, evidence_confidence = (
                    self._evidence_to_skill_level(
                        evidence_ratio,
                        total_signals,
                    )
                )

                gap = max(target_level - current_level, 0)
                gap_label = self._gap_label(gap)
                priority = self._priority_for_gap(gap)

            item = {
                "skill_id": skill_id,
                "skill_name": skill_name,
                "category": category,
                "weight": weight,
                "current_level": current_level,
                "current_level_label": (
                    SKILL_LEVEL_LABELS[current_level]
                    if current_level is not None
                    else "No Evidence"
                ),
                "target_level": target_level,
                "evidence_ratio": (
                    round(evidence_ratio, 2)
                    if evidence_ratio is not None
                    else None
                ),
                "positive_signals": positive_signals,
                "negative_signals": negative_signals,
                "total_signals": total_signals,
                "evidence_questions": question_ids,
                "gap": gap,
                "gap_label": gap_label,
                "priority": priority,
                "evidence_status": (
                    "measured" if total_signals > 0 else "no_evidence"
                ),
                "evidence_confidence": (
                    evidence_confidence if total_signals > 0 else "none"
                ),
            }

            result.append(item)

            if current_level is not None and current_level >= target_level:
                strength_items.append(item)

            if gap is not None and gap > 0:
                weak_skill_items.append(item)

        strength_items.sort(
            key=lambda item: (
                -item["current_level"],
                CATEGORY_ORDER.get(item["category"], 9),
                item["skill_name"],
            )
        )

        weak_skill_items.sort(
            key=lambda item: (
                -item["gap"],
                CATEGORY_ORDER.get(item["category"], 9),
                item["skill_name"],
            )
        )

        return {
            "skills": result,
            "strengths": [item["skill_name"] for item in strength_items],
            "weak_areas": [item["skill_name"] for item in weak_skill_items],
        }

    @staticmethod
    def _display_skill_name(skill_id: str) -> str:
        """Convert canonical snake_case skill IDs to readable names."""
        return skill_id.replace("_", " ").title()

    # ========================================================
    # EVIDENCE → SKILL LEVEL
    # ========================================================

    def _evidence_to_skill_level(
        self,
        evidence_ratio: float,
        evidence_count: int,
    ) -> tuple[int, str]:
        """
        Convert assessment evidence into a conservative 1-5 skill level.

        Existing ratio thresholds are preserved, but evidence quantity now
        limits how high the system can claim:
            1 evidence question -> maximum Level 3 (Intermediate)
            2 evidence questions -> maximum Level 4 (Advanced)
            3+ evidence questions -> normal ratio conversion

        Returns:
            (skill_level, evidence_confidence)
        """

        conversion = (
            self.skills_config
            .get("skill_level_calculation", {})
            .get("conversion", [])
        )

        level = None

        for rule in conversion:
            minimum = float(rule.get("evidence_min", 0.0))
            maximum = float(rule.get("evidence_max", 1.0))

            if minimum <= evidence_ratio <= maximum:
                level = int(rule.get("level", 1))
                break

        if level is None:
            if evidence_ratio >= 0.80:
                level = 5
            elif evidence_ratio >= 0.60:
                level = 4
            elif evidence_ratio >= 0.40:
                level = 3
            elif evidence_ratio >= 0.20:
                level = 2
            else:
                level = 1

        level = max(1, min(5, level))

        if evidence_count <= 1:
            level = min(level, 3)
            confidence = "low"
        elif evidence_count == 2:
            level = min(level, 4)
            confidence = "moderate"
        else:
            confidence = "high"

        return level, confidence

    # GAP LABEL
    # ========================================================

    def _gap_label(
        self,
        gap: int,
    ) -> str:
        """
        Get gap label from journey_2_skills.json.
        """

        gap_rules = (
            self.skills_config
            .get(
                "skill_gap_logic",
                {},
            )
            .get(
                "gap_labels",
                [],
            )
        )

        for rule in gap_rules:

            minimum = int(
                rule.get(
                    "min_gap",
                    0,
                )
            )

            maximum = int(
                rule.get(
                    "max_gap",
                    0,
                )
            )

            if minimum <= gap <= maximum:

                return str(
                    rule.get(
                        "label",
                        "Unknown",
                    )
                )

        # Safe fallback.
        if gap == 0:
            return "No Gap"

        if gap == 1:
            return "Low Gap"

        if gap == 2:
            return "Moderate Gap"

        return "High Gap"

    # ========================================================
    # PRIORITY
    # ========================================================

    def _priority_for_gap(
        self,
        gap: int,
    ) -> str:
        """
        Determine skill priority using
        skill_gap_logic.priority_rules.
        """

        priority_rules = (
            self.skills_config
            .get(
                "skill_gap_logic",
                {},
            )
            .get(
                "priority_rules",
                [],
            )
        )

        # The config is written from highest gap to lowest.
        for rule in priority_rules:

            condition = str(
                rule.get(
                    "condition",
                    "",
                )
            ).strip()

            priority = str(
                rule.get(
                    "priority",
                    "None",
                )
            )

            if condition == "gap >= 3":
                if gap >= 3:
                    return priority.title()

            elif condition == "gap == 2":
                if gap == 2:
                    return priority.title()

            elif condition == "gap == 1":
                if gap == 1:
                    return priority.title()

            elif condition == "gap == 0":
                if gap == 0:
                    return priority.title()

        # Safe fallback.
        if gap >= 3:
            return "High"

        if gap == 2:
            return "Medium"

        if gap == 1:
            return "Low"

        return "None"

    # ========================================================
    # SKILL GAP
    # ========================================================

    def _build_skill_gap(
        self,
        career: str,
        current_profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Build measured canonical skill gaps.

        Skills with no assessment evidence are excluded from the formal gap
        list because lack of evidence is not proof of a skill level of 1.
        They remain visible in ``current_skill_profile`` with
        ``evidence_status='no_evidence'``.
        """

        _ = career
        gaps: List[Dict[str, Any]] = []

        for skill in current_profile["skills"]:
            missing = skill.get("gap")

            if missing is None or int(missing) <= 0:
                continue

            gaps.append(
                {
                    "skill_id": skill["skill_id"],
                    "skill_name": skill["skill_name"],
                    "category": skill.get("category", "supporting"),
                    "weight": skill.get("weight", 1.0),
                    "current_level": skill["current_level"],
                    "required_level": skill["target_level"],
                    "missing_levels": int(missing),
                    "gap_label": skill["gap_label"],
                    "priority": skill["priority"],
                    "evidence_ratio": skill["evidence_ratio"],
                    "evidence_questions": skill.get("evidence_questions", []),
                }
            )

        gaps.sort(
            key=lambda item: (
                PRIORITY_ORDER.get(item["priority"], 9),
                -item["missing_levels"],
                CATEGORY_ORDER.get(item["category"], 9),
                item["skill_name"],
            )
        )

        return gaps

    # ========================================================
    # RECOMMENDED NEXT STEP
    # ========================================================

    def _recommended_next_step(
        self,
        readiness: float,
        skill_gap: List[Dict[str, Any]],
    ) -> str:
        """
        Generate the next-step recommendation using the
        recommended_next_step_rules in journey_2_skills.json.
        """

        readiness_rules = self.skills_config.get(
            "recommended_next_step_rules",
            [],
        )

        has_high_priority_gap = any(
            item.get("priority") == "High"
            for item in skill_gap
        )

        # ----------------------------------------------------
        # Rule 1:
        # High-priority gaps exist
        # ----------------------------------------------------

        if has_high_priority_gap:

            for rule in readiness_rules:

                condition = rule.get(
                    "condition"
                )

                if condition == "high_priority_gaps_exist":

                    return str(
                        rule.get(
                            "message",
                            "Focus first on your highest-priority core skill gaps.",
                        )
                    )

            return (
                "Focus first on your highest-priority "
                "core skill gaps."
            )

        # ----------------------------------------------------
        # Rule 4:
        # 100% readiness
        # ----------------------------------------------------

        if readiness >= 100:

            for rule in readiness_rules:

                if rule.get("condition") == "readiness_100":

                    return str(
                        rule.get(
                            "message",
                            "Validate your readiness through a practical project rather than relying on assessment performance alone.",
                        )
                    )

            return (
                "Validate your readiness through a practical "
                "project rather than relying on assessment "
                "performance alone."
            )

        # ----------------------------------------------------
        # Rule 3:
        # At least 80%
        # ----------------------------------------------------

        if readiness >= 80:

            for rule in readiness_rules:

                if rule.get(
                    "condition"
                ) == "readiness_at_least_80":

                    return str(
                        rule.get(
                            "message",
                            "Move toward practical projects and deeper career-specific practice.",
                        )
                    )

            return (
                "Move toward practical projects and deeper "
                "career-specific practice."
            )

        # ----------------------------------------------------
        # Rule 2:
        # Below 80% and no high-priority gaps
        # ----------------------------------------------------

        for rule in readiness_rules:

            if rule.get(
                "condition"
            ) == "no_high_priority_gaps_and_readiness_below_80":

                return str(
                    rule.get(
                        "message",
                        "Strengthen the skills marked Developing or Functional through guided practice.",
                    )
                )

        return (
            "Strengthen the skills marked Developing or "
            "Functional through guided practice."
        )


# ============================================================
# ENGINE FACTORY
# ============================================================

def build_engine(
    assessment_path: str | Path = "assessment.json",
    skills_path: str | Path = "journey_2_skills.json",
    matrix_path: str | Path = "career_skill_matrix.json",
    normalization_path: str | Path = "skill_normalization.json",
) -> Journey2ScoringEngine:
    """
    Convenience factory used by backend code.
    """

    return Journey2ScoringEngine(
        assessment_path=assessment_path,
        skills_path=skills_path,
        matrix_path=matrix_path,
        normalization_path=normalization_path,
    )


# ============================================================
# LOCAL SMOKE TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("MINERVA JOURNEY 2 — CAREER-IN-MIND ENGINE")
    print("=" * 70)

    try:

        # ----------------------------------------------------
        # Build engine
        # ----------------------------------------------------

        engine = build_engine()

        print("\n[1/5] Configuration validation: PASSED")

        # ----------------------------------------------------
        # Test selected career
        # ----------------------------------------------------

        career = "data"

        questions = engine.get_career_questions(
            career
        )

        print(
            f"[2/5] Loaded career '{career}' "
            f"with {len(questions)} public questions."
        )

        # ----------------------------------------------------
        # Verify answer keys are not exposed
        # ----------------------------------------------------

        exposed_keys = []

        for question in questions:

            if "correct_option" in question:
                exposed_keys.append(
                    question["id"]
                )

            if "score" in question:
                exposed_keys.append(
                    f"{question['id']}:score"
                )

        if exposed_keys:

            raise InvalidAssessmentError(
                "Security check failed. "
                f"Public questions expose: {exposed_keys}"
            )

        print(
            "[3/5] Frontend security check: PASSED "
            "(answer keys hidden)"
        )

        # ----------------------------------------------------
        # Local smoke test
        #
        # Uses actual correct answers ONLY locally.
        # These answers are never returned to frontend.
        # ----------------------------------------------------

        raw_questions = engine.assessment[
            "questions"
        ]["career_in_mind"][career]

        test_answers = {
            question["id"]: question["correct_option"]
            for question in raw_questions
        }

        result = engine.score_assessment(
            career=career,
            answers=test_answers,
        )

        # ----------------------------------------------------
        # Verify perfect score
        # ----------------------------------------------------

        if result["score"] != 5:
            raise InvalidAssessmentError(
                "Smoke test failed: expected score 5."
            )

        if result["max_score"] != 5:
            raise InvalidAssessmentError(
                "Smoke test failed: expected max_score 5."
            )

        if result["readiness_percent"] != 100:
            raise InvalidAssessmentError(
                "Smoke test failed: expected readiness 100%."
            )

        print(
            "[4/5] Scoring smoke test: PASSED "
            "(5/5 = 100%)"
        )

        # ----------------------------------------------------
        # Verify result structure
        # ----------------------------------------------------

        required_result_keys = {
            "career",
            "career_name",
            "score",
            "max_score",
            "readiness_percent",
            "performance_level",
            "performance_label",
            "validation",
            "strengths",
            "weak_areas",
            "current_skill_profile",
            "skill_gap",
            "question_results",
            "recommended_next_step",
        }

        missing_result_keys = (
            required_result_keys
            - set(result.keys())
        )

        if missing_result_keys:

            raise InvalidAssessmentError(
                "Smoke test failed. Missing result keys: "
                f"{sorted(missing_result_keys)}"
            )

        print(
            "[5/5] Result contract check: PASSED"
        )

        print("\n" + "=" * 70)
        print("ALL JOURNEY 2 SMOKE TESTS PASSED")
        print("=" * 70)

        print(
            "\nCareer:",
            result["career_name"],
        )

        print(
            "Score:",
            f"{result['score']}/{result['max_score']}",
        )

        print(
            "Readiness:",
            f"{result['readiness_percent']}%",
        )

        print(
            "Performance:",
            result["performance_level"],
        )

        print(
            "Validation:",
            result["validation"],
        )

        print(
            "\nStrengths:"
        )

        for strength in result["strengths"]:
            print(
                f"  + {strength}"
            )

        print(
            "\nWeak Areas:"
        )

        for weak_area in result["weak_areas"]:
            print(
                f"  - {weak_area}"
            )

        print(
            "\nSkill Gaps:"
        )

        for gap in result["skill_gap"]:
            print(
                f"  - {gap['skill_name']}: "
                f"gap={gap['missing_levels']}, "
                f"priority={gap['priority']}"
            )

        print(
            "\nRecommended Next Step:"
        )

        print(
            f"  {result['recommended_next_step']}"
        )

        print(
            "\nFull JSON Result:"
        )

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )

    except Exception as exc:

        print("\n" + "=" * 70)
        print("JOURNEY 2 ENGINE FAILED")
        print("=" * 70)

        print(
            f"\nError Type: {type(exc).__name__}"
        )

        print(
            f"Error: {exc}"
        )

        raise