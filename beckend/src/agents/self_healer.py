"""Self-Healing Agent - Autonomous DAX correction based on validation failures"""
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from loguru import logger

from src.llm_reasoner import LLMReasoner
from api.models.migration_models import ErrorCategory


@dataclass
class CorrectionAttempt:
    """Record of a correction attempt"""
    attempt_number: int
    original_dax: str
    corrected_dax: str
    root_cause: str
    explanation: str
    changes_made: List[str]


@dataclass
class FailureAnalysis:
    """Analysis of validation failures"""
    error_categories: Dict[str, int]  # Category -> count
    common_patterns: List[str]
    suggested_fixes: List[str]
    confidence: float


class SelfHealingAgent:
    """
    Autonomous agent that analyzes validation failures and corrects DAX code

    Design Philosophy:
    - Use LLM reasoning to understand WHY validation failed
    - Apply domain knowledge (Tableau → DAX patterns)
    - Iteratively refine until tests pass
    - Learn from corrections (future: store patterns)

    Key Features:
    1. Error Categorization → Root Cause Analysis
    2. Pattern-Based Suggestions
    3. Chain-of-Thought Reasoning
    4. Explanation Generation for transparency
    """

    def __init__(self, max_attempts: int = 3):
        """
        Initialize self-healing agent

        Args:
            max_attempts: Maximum correction attempts per conversion
        """
        self.max_attempts = max_attempts
        self.llm_reasoner = LLMReasoner()
        self.correction_history: List[CorrectionAttempt] = []

        logger.info(f"Self-Healing Agent initialized (max attempts: {max_attempts})")

    # ============================================
    # Main Correction Method
    # ============================================

    def correct_dax(
        self,
        original_tableau: str,
        failed_dax: str,
        failures: List[Any],  # List of TestSlice objects
        attempt_number: int,
        context: Optional[Dict[str, Any]] = None
    ) -> CorrectionAttempt:
        """
        Generate corrected DAX based on validation failures

        Args:
            original_tableau: Original Tableau formula
            failed_dax: DAX that failed validation
            failures: List of failed test slices
            attempt_number: Current attempt number
            context: Optional context (visual type, data profile, etc.)

        Returns:
            CorrectionAttempt with new DAX and explanation
        """
        logger.info(f"🔧 Self-healing attempt {attempt_number}/{self.max_attempts}")

        # Step 1: Analyze failures
        analysis = self._analyze_failures(failures)

        logger.info(f"  Error categories: {analysis.error_categories}")
        logger.info(f"  Suggested fixes: {', '.join(analysis.suggested_fixes)}")

        # Step 2: Build correction prompt
        prompt = self._build_correction_prompt(
            original_tableau=original_tableau,
            failed_dax=failed_dax,
            failures=failures,
            analysis=analysis,
            attempt_number=attempt_number,
            context=context
        )

        # Step 3: Get LLM correction
        try:
            response = self.llm_reasoner.reason(prompt)

            # Parse response
            correction_data = self._parse_llm_response(response)

            # Create correction attempt record
            attempt = CorrectionAttempt(
                attempt_number=attempt_number,
                original_dax=failed_dax,
                corrected_dax=correction_data.get("corrected_dax", failed_dax),
                root_cause=correction_data.get("root_cause", "Unknown"),
                explanation=correction_data.get("explanation", ""),
                changes_made=correction_data.get("changes", [])
            )

            self.correction_history.append(attempt)

            logger.info(f"✅ Correction generated")
            logger.info(f"  Root cause: {attempt.root_cause}")
            logger.info(f"  Changes: {', '.join(attempt.changes_made)}")

            return attempt

        except Exception as e:
            logger.error(f"❌ Self-correction failed: {e}")

            # Return original DAX if correction fails
            return CorrectionAttempt(
                attempt_number=attempt_number,
                original_dax=failed_dax,
                corrected_dax=failed_dax,  # No change
                root_cause=f"Correction failed: {e}",
                explanation="Unable to generate correction",
                changes_made=[]
            )

    # ============================================
    # Failure Analysis
    # ============================================

    def _analyze_failures(self, failures: List[Any]) -> FailureAnalysis:
        """
        Analyze validation failures to identify patterns

        Args:
            failures: List of TestSlice objects

        Returns:
            FailureAnalysis with categorized errors and suggestions
        """
        # Count error categories
        error_counts = {}
        for failure in failures:
            category = failure.error_category.value
            error_counts[category] = error_counts.get(category, 0) + 1

        # Identify common patterns
        common_patterns = []
        suggested_fixes = []

        # Pattern: All failures are scale errors → likely percentage issue
        if error_counts.get("SCALE_ERROR", 0) == len(failures):
            common_patterns.append("All failures are scale errors (10x, 100x difference)")
            suggested_fixes.append("Check if you're calculating percentages vs. decimals")
            suggested_fixes.append("Multiply or divide by 100 if needed")

        # Pattern: All failures are context shifts → likely filter context issue
        if error_counts.get("CONTEXT_SHIFT", 0) == len(failures):
            common_patterns.append("All failures are context shifts (>10% error)")
            suggested_fixes.append("Review CALCULATE filter context")
            suggested_fixes.append("Check if you need KEEPFILTERS, ALL, or ALLEXCEPT")

        # Pattern: Null handling issues
        if error_counts.get("NULL_HANDLING", 0) > 0:
            common_patterns.append("Null handling differs between Tableau and DAX")
            suggested_fixes.append("Use DIVIDE() instead of / operator")
            suggested_fixes.append("Add COALESCE or ISBLANK checks")

        # Pattern: Grain mismatch → LOD issue
        if error_counts.get("GRAIN_MISMATCH", 0) > 0:
            common_patterns.append("Grain mismatch detected (likely LOD conversion issue)")
            suggested_fixes.append("Review FIXED/INCLUDE/EXCLUDE conversion")
            suggested_fixes.append("Check aggregation level (measure vs. calculated column)")

        # Calculate confidence based on pattern clarity
        if len(set(error_counts.keys())) == 1:
            # All failures are same category → high confidence
            confidence = 0.9
        elif len(common_patterns) > 0:
            confidence = 0.7
        else:
            confidence = 0.5

        return FailureAnalysis(
            error_categories=error_counts,
            common_patterns=common_patterns,
            suggested_fixes=suggested_fixes,
            confidence=confidence
        )

    # ============================================
    # Prompt Engineering
    # ============================================

    def _build_correction_prompt(
        self,
        original_tableau: str,
        failed_dax: str,
        failures: List[Any],
        analysis: FailureAnalysis,
        attempt_number: int,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build detailed correction prompt for LLM"""

        # Build failure summary
        failure_details = []
        for i, failure in enumerate(failures[:5], 1):  # Show max 5 examples
            failure_details.append(f"""
**Failure {i}:**
- Dimensions: {failure.dimensions}
- Expected (Tableau): {failure.tableau_value}
- Got (DAX): {failure.dax_value}
- Delta: {failure.delta:.4f} ({failure.relative_error:.2%} error)
- Error Type: {failure.error_category.value}
""")

        failure_summary = "\n".join(failure_details)

        prompt = f"""You are an expert DAX debugger specializing in Tableau-to-Power BI migrations.

## CONTEXT

You are on correction attempt {attempt_number} of {self.max_attempts}.

## ORIGINAL TABLEAU FORMULA

```tableau
{original_tableau}
```

## YOUR GENERATED DAX (FAILED VALIDATION)

```dax
{failed_dax}
```

## VALIDATION FAILURES ({len(failures)} slices failed)

{failure_summary}

## FAILURE ANALYSIS

**Error Distribution:**
{json.dumps(analysis.error_categories, indent=2)}

**Patterns Detected:**
{chr(10).join(f"- {p}" for p in analysis.common_patterns)}

**Suggested Fixes:**
{chr(10).join(f"- {f}" for f in analysis.suggested_fixes)}

**Analysis Confidence:** {analysis.confidence:.0%}

## YOUR TASK

Generate a CORRECTED DAX formula that will pass validation.

**Critical Checks:**

1. **Filter Context:**
   - Tableau LOD FIXED → Use CALCULATE with ALL/ALLEXCEPT
   - Tableau LOD INCLUDE → Use CALCULATE with KEEPFILTERS
   - Tableau LOD EXCLUDE → Use CALCULATE with REMOVEFILTERS

2. **Null Handling:**
   - Always use DIVIDE(numerator, denominator, 0) instead of numerator/denominator
   - Consider COALESCE for nullable columns

3. **Aggregation Level:**
   - Tableau calculated fields default to aggregated context
   - Ensure you're using SUM([Column]) not just [Column]

4. **Scale/Units:**
   - If scale error, check percentage vs. decimal (multiply/divide by 100)

5. **Row Context:**
   - If grain mismatch, you may need SUMX/AVERAGEX instead of SUM/AVERAGE

## OUTPUT FORMAT

Return ONLY valid JSON (no markdown, no extra text):

{{
  "root_cause": "Brief description of what caused the failures",
  "corrected_dax": "YourMeasure = <complete DAX formula here>",
  "explanation": "Detailed explanation of what you changed and why",
  "changes": ["Change 1", "Change 2", "Change 3"]
}}

**Example:**
{{
  "root_cause": "Missing DIVIDE safety and wrong filter context for LOD",
  "corrected_dax": "Profit Ratio = DIVIDE(SUM(Sales[Profit]), SUM(Sales[Revenue]), 0)",
  "explanation": "Changed to DIVIDE() to handle division by zero safely, matching Tableau's ZN() behavior",
  "changes": ["Added DIVIDE function", "Added 0 as default value"]
}}

Generate your correction now:
"""

        return prompt

    # ============================================
    # Response Parsing
    # ============================================

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM correction response

        Args:
            response: Raw LLM response

        Returns:
            Dict with corrected_dax, root_cause, explanation, changes
        """
        # Clean response (remove markdown if present)
        cleaned = response.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)

            return {
                "corrected_dax": data.get("corrected_dax", ""),
                "root_cause": data.get("root_cause", "Unknown"),
                "explanation": data.get("explanation", ""),
                "changes": data.get("changes", [])
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {cleaned[:200]}")

            # Fallback: try to extract DAX from response
            return {
                "corrected_dax": self._extract_dax_fallback(response),
                "root_cause": "JSON parse failed",
                "explanation": response[:500],
                "changes": []
            }

    def _extract_dax_fallback(self, response: str) -> str:
        """Extract DAX formula from unstructured response"""
        # Look for DAX code block
        import re

        dax_match = re.search(r'```dax\n(.+?)\n```', response, re.DOTALL)
        if dax_match:
            return dax_match.group(1).strip()

        # Look for assignment pattern
        assignment_match = re.search(r'(\w+)\s*=\s*(.+)', response, re.DOTALL)
        if assignment_match:
            return f"{assignment_match.group(1)} = {assignment_match.group(2).strip()}"

        return ""

    # ============================================
    # Utility Methods
    # ============================================

    def get_correction_summary(self) -> Dict[str, Any]:
        """Get summary of all corrections made"""
        return {
            "total_attempts": len(self.correction_history),
            "attempts": [
                {
                    "attempt": attempt.attempt_number,
                    "root_cause": attempt.root_cause,
                    "changes": attempt.changes_made
                }
                for attempt in self.correction_history
            ]
        }


# ============================================
# Convenience Function
# ============================================

def auto_correct_dax(
    tableau_formula: str,
    failed_dax: str,
    failures: List[Any],
    max_attempts: int = 3
) -> str:
    """
    Quick correction function

    Args:
        tableau_formula: Original Tableau formula
        failed_dax: DAX that failed
        failures: Failed test slices
        max_attempts: Max correction loops

    Returns:
        Corrected DAX formula
    """
    agent = SelfHealingAgent(max_attempts=max_attempts)

    attempt = agent.correct_dax(
        original_tableau=tableau_formula,
        failed_dax=failed_dax,
        failures=failures,
        attempt_number=1
    )

    return attempt.corrected_dax


if __name__ == "__main__":
    print("Self-Healing Agent - Test Mode\n")

    # Mock test
    print("This agent requires:")
    print("1. Validation failures from ValidationEngine")
    print("2. LLM reasoning capability (Azure OpenAI)")
    print("3. Integration with migration orchestrator")
    print("\nUse validate_conversion_v2() in ValidationEngine to trigger self-healing.")
