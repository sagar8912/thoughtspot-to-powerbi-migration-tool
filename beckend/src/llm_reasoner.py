"""
LLM Semantic Reasoning Layer - LangChain Implementation.
Uses Azure OpenAI via LangChain for semantic validation.
"""

import os
import json
from typing import Dict, Any, Optional
from loguru import logger

from src.config import Config


class LLMReasoner:
    """
    LLM-based semantic reasoning for relationship validation.
    Uses LangChain with Azure OpenAI for robust, standardized LLM calls.
    """
    
    def __init__(self):
        self.api_key = Config.AZURE_OPENAI_API_KEY
        self.endpoint = Config.AZURE_OPENAI_ENDPOINT
        self.deployment = Config.AZURE_OPENAI_DEPLOYMENT_NAME
        self.llm = None
        
        if not Config.ENABLE_LLM_VALIDATION:
            logger.warning("LLM validation is disabled in configuration")
            return
        
        if not self.endpoint or not self.api_key:
            logger.warning(
                "Azure OpenAI credentials not configured. "
                "LLM validation will be skipped."
            )
            return
        
        # Initialize LangChain LLM
        try:
            from langchain_openai import ChatOpenAI

            self.llm = ChatOpenAI(
                model=self.deployment,
                api_key=self.api_key,
                base_url=self.endpoint,
                temperature=Config.LLM_TEMPERATURE,
                max_tokens=Config.LLM_MAX_TOKENS,
                model_kwargs={
                    "response_format": {"type": "json_object"}  # FORCE JSON MODE
                }
            )

            logger.debug(f"LLM initialized with JSON mode: {self.deployment}")

        except ImportError:
            logger.error("langchain-openai not installed. Run: pip install langchain-openai")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
    
    def validate_relationship(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a relationship candidate using LLM semantic reasoning.
        
        Args:
            candidate: Dictionary with source, target, and statistics
            
        Returns:
            Dictionary with validation result
        """
        if not Config.ENABLE_LLM_VALIDATION or not self.llm:
            return self._get_fallback_result("LLM not available")
        
        try:
            # Build prompt
            prompt = self._build_validation_prompt(candidate)
            
            # Call LLM via LangChain
            response = self.llm.invoke(prompt)
            
            # Parse JSON response
            result = json.loads(response.content)
            
            logger.debug(f"LLM validated: {candidate['source']['column']} <-> {candidate['target']['column']}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"LLM returned invalid JSON: {e}")
            return self._get_fallback_result(f"Invalid JSON response")
        except Exception as e:
            logger.error(f"LLM validation failed: {e}")
            return self._get_fallback_result(f"Error: {str(e)}")

    def reason(self, prompt: str) -> str:
        """
        Generic reasoning method for DAX generation and other tasks.

        Args:
            prompt: The prompt to send to the LLM

        Returns:
            String response from the LLM
        """
        if not Config.ENABLE_LLM_VALIDATION or not self.llm:
            raise Exception("LLM not available - check Azure OpenAI configuration")

        try:
            # Call LLM via LangChain
            response = self.llm.invoke(prompt)
            return response.content

        except Exception as e:
            logger.error(f"LLM reasoning failed: {e}")
            raise

    def _build_validation_prompt(self, candidate: Dict[str, Any]) -> str:
        """Build structured prompt for relationship validation."""
        
        source = candidate["source"]
        target = candidate["target"]
        stats = candidate.get("statistics", {})
        
        # Get sample values (limit to 5)
        source_samples = source.get("sample_values", [])[:5]
        target_samples = target.get("sample_values", [])[:5]
        
        prompt = f"""Analyze this potential column relationship:

SOURCE COLUMN:
- File: {source['file']}
- Column: {source['column']}
- Data type: {source.get('data_type', 'unknown')}
- Sample values: {source_samples}
- Uniqueness: {source.get('uniqueness', 0):.1%}
- NULL %: {source.get('null_percent', 0):.1%}

TARGET COLUMN:
- File: {target['file']}
- Column: {target['column']}
- Data type: {target.get('data_type', 'unknown')}
- Sample values: {target_samples}
- Uniqueness: {target.get('uniqueness', 0):.1%}
- NULL %: {target.get('null_percent', 0):.1%}

OVERLAP STATISTICS:
- Value overlap: {stats.get('value_overlap_percent', 0):.1f}%
- Orphan records: {stats.get('orphans_in_source', 0) + stats.get('orphans_in_target', 0)}

INSTRUCTIONS:
Determine if these columns are semantically related and can be joined.
Respond ONLY with valid JSON in this EXACT format (no markdown, no code blocks):

{{
  "is_related": true or false,
  "relationship_type": "PRIMARY_KEY -> FOREIGN_KEY" or "SEMANTIC_MATCH" or "NONE",
  "cardinality": "1:1" or "1:N" or "N:1" or "M:N" or "UNKNOWN",
  "confidence_score": 0-100,
  "reasoning": "Brief explanation in one sentence",
  "warnings": ["warning1", "warning2"] or [],
  "transformation_needed": null or "UPPER()" or "STRIP_PREFIX()"
}}"""
        
        return prompt
    
    def _get_fallback_result(self, reason: str) -> Dict[str, Any]:
        """Return conservative fallback when LLM is unavailable."""
        return {
            "is_related": False,
            "relationship_type": "UNKNOWN",
            "cardinality": "UNKNOWN",
            "confidence_score": 0,
            "reasoning": f"LLM validation unavailable: {reason}",
            "warnings": ["LLM unavailable, using deterministic rules only"],
            "transformation_needed": None
        }

    def check_semantic_duplicate(self, col1_data: Dict[str, Any], col2_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check if two columns are semantically duplicate using LLM.

        Args:
            col1_data: Dictionary with keys: name, data_type, samples, overlap_percent
            col2_data: Dictionary with keys: name, data_type, samples

        Returns:
            Dictionary with semantic_match, confidence, reasoning, recommendation
        """
        if not self.llm:
            return self._get_semantic_fallback("LLM not initialized")

        try:
            # Build prompt
            prompt = f"""Analyze if these two columns represent the SAME semantic concept:

Column 1: '{col1_data['name']}' (type: {col1_data['data_type']})
Sample values: {col1_data['samples'][:10]}

Column 2: '{col2_data['name']}' (type: {col2_data['data_type']})
Sample values: {col2_data['samples'][:10]}

Data Overlap: {col1_data.get('overlap_percent', 0):.1f}%

Consider:
1. Do they represent the same business entity/attribute?
2. Are the sample values semantically equivalent?
3. Would keeping both columns create redundancy?

Respond ONLY with valid JSON (no markdown, no code blocks):
{{
  "semantic_match": true or false,
  "confidence": 0-100,
  "reasoning": "brief explanation",
  "recommendation": "keep first" or "keep second" or "keep both"
}}"""

            # Call LLM
            response = self.llm.invoke(prompt)

            if not response or not response.content:
                return self._get_semantic_fallback("Empty LLM response")

            # Parse JSON response
            result = json.loads(response.content.strip())

            logger.debug(f"Semantic duplicate check: {col1_data['name']} vs {col2_data['name']} = {result['semantic_match']} ({result['confidence']}%)")

            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return self._get_semantic_fallback("Invalid JSON response")
        except Exception as e:
            logger.error(f"Semantic duplicate check failed: {e}")
            return self._get_semantic_fallback(str(e))

    def _get_semantic_fallback(self, reason: str) -> Dict[str, Any]:
        """Return fallback response when LLM is unavailable for semantic checking."""
        return {
            "semantic_match": False,
            "confidence": 0,
            "reasoning": f"LLM unavailable: {reason}",
            "recommendation": "keep both"
        }

    def test_connection(self) -> bool:
        """
        Test connection to Azure OpenAI.
        
        Returns:
            bool: True if connection successful
        """
        if not self.llm:
            logger.error("LLM not initialized - check configuration")
            return False
        
        try:
            # Simple test query
            response = self.llm.invoke("Respond with just the word 'OK' if you can read this.")
            
            if response and response.content:
                logger.success("✓ Azure OpenAI connection successful")
                logger.info(f"  Model: {self.deployment}")
                logger.info(f"  Response: {response.content[:50]}")
                return True
            else:
                logger.error("✗ Azure OpenAI returned empty response")
                return False
                
        except Exception as e:
            logger.error(f"✗ Azure OpenAI connection failed: {e}")
            return False
